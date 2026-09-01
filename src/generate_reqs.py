"""PART 1 driver — generate a traceable requirement set for the target functionality.

    python -m src.generate_reqs
    python -m src.generate_reqs --model secondary --dry-run

Contract enforcement is deliberately split in two:

  * Integrity is enforced HERE and is fatal. Fabricated chunk_ids, an empty
    citation list on a requirement claiming not to be derived, broken enums — these
    corrupt the traceability record, so the driver repairs once and then fails loud.

  * Requirement QUALITY (weak words, compound obligations, unverifiable acceptance
    criteria) is deliberately NOT enforced here. It is measured by validate.py
    against ISO/IEC/IEEE 29148. Repairing quality at generation time would launder
    the model's output and leave the audit with nothing to find, which is precisely
    the finding the report exists to report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

from . import ensure_dir, load_pipeline, resolve
from .index import retrieve_evidence
from .llm import LLMError, OllamaClient

ENUMS: dict[str, set[str]] = {
    "type": {"FR", "NFR"},
    "nfr_category": {
        "security",
        "performance",
        "reliability",
        "usability",
        "compliance",
        "maintainability",
        "portability",
        "none",
    },
    "actor": {"prescriber", "pharmacist", "patient", "system", "auditor"},
    "priority": {"Must", "Should", "Could", "Won't"},
    "verification_method": {"Test", "Demonstration", "Inspection", "Analysis"},
    "risk_class": {"Safety-critical", "Business-critical", "Standard"},
    "volatility": {"High", "Medium", "Low"},
    "inference_type": {
        "direct_extraction",
        "generalization",
        "domain_inference",
        "regulatory_derivation",
    },
}

REQ_COLUMNS = [
    "req_id",
    "type",
    "nfr_category",
    "statement",
    "actor",
    "priority",
    "verification_method",
    "acceptance_criteria",
    "risk_class",
    "volatility",
    "source_chunk_ids",
    "derived",
]
REASONING_COLUMNS = ["req_id", "reasoning", "evidence_quote", "inference_type"]


def load_prompt(name: str) -> str:
    return (resolve("prompts") / name).read_text(encoding="utf-8")


def render(template: str, **fields: str) -> str:
    """Substitute {PLACEHOLDER} tokens.

    str.format() is unusable here: the prompt embeds a literal JSON skeleton, and
    every brace in it would be read as a format field.
    """
    out = template
    for key, value in fields.items():
        out = out.replace("{" + key + "}", value)
    return out


def guard_write(path: Path) -> Path:
    if os.environ.get("PROTECT_OUTPUTS") == "1" and path.exists():
        raise FileExistsError(
            f"{path} exists and PROTECT_OUTPUTS=1. Generated artifacts are evidence; "
            "move the existing file aside deliberately rather than overwriting it."
        )
    ensure_dir(path.parent)
    return path


def build_evidence(hits, budget: int) -> tuple[str, list[str]]:
    """Format retrieved chunks as labelled evidence, respecting a token budget.

    Returns the evidence block and the chunk_ids actually shown — the second value
    is what 'a real chunk_id' means when the response is validated, so a chunk that
    was retrieved but dropped for budget cannot be cited.
    """
    blocks: list[str] = []
    shown: list[str] = []
    used = 0

    for h in hits:
        if used + h.token_count > budget and shown:
            break
        blocks.append(
            f"[chunk_id: {h.chunk_id}]  (source {h.doc_id}, section {h.section} — {h.heading})\n"
            f"{h.text}"
        )
        shown.append(h.chunk_id)
        used += h.token_count

    return "\n\n---\n\n".join(blocks), shown


def validate_payload(
    payload: Any, valid_chunk_ids: set[str], cfg: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Check the model's JSON against the output contract.

    Returns (records, errors). Errors are integrity failures only; requirement
    quality is out of scope here by design.
    """
    errors: list[str] = []

    if not isinstance(payload, dict) or "requirements" not in payload:
        return [], ["top-level JSON must be an object with a 'requirements' array"]
    reqs = payload["requirements"]
    if not isinstance(reqs, list) or not reqs:
        return [], ["'requirements' must be a non-empty array"]

    gen = cfg["generation"]
    if not (gen["min_requirements"] <= len(reqs) <= gen["max_requirements"]):
        errors.append(
            f"produced {len(reqs)} requirements; contract requires between "
            f"{gen['min_requirements']} and {gen['max_requirements']}"
        )

    n_nfr = sum(1 for r in reqs if isinstance(r, dict) and r.get("type") == "NFR")
    if n_nfr < gen["min_nfrs"]:
        errors.append(f"only {n_nfr} NFRs; contract requires at least {gen['min_nfrs']}")

    seen: set[str] = set()
    records: list[dict[str, Any]] = []

    for i, r in enumerate(reqs, start=1):
        if not isinstance(r, dict):
            errors.append(f"requirement #{i} is not an object")
            continue

        rid = str(r.get("req_id", "")).strip()
        label = rid or f"#{i}"

        if not re.fullmatch(r"(FR|NFR)-\d{2,}", rid):
            errors.append(f"{label}: req_id must look like FR-01 or NFR-01")
        if rid in seen:
            errors.append(f"{label}: duplicate req_id")
        seen.add(rid)

        for field, allowed in ENUMS.items():
            val = r.get(field)
            if val not in allowed:
                errors.append(f"{label}: {field}={val!r} is not one of {sorted(allowed)}")

        rtype = r.get("type")
        cat = r.get("nfr_category")
        if rtype == "FR" and cat != "none":
            errors.append(f"{label}: FR must have nfr_category 'none', got {cat!r}")
        if rtype == "NFR" and cat == "none":
            errors.append(f"{label}: NFR must have a real nfr_category, got 'none'")
        if rid.startswith("FR-") and rtype != "FR":
            errors.append(f"{label}: req_id prefix disagrees with type={rtype!r}")
        if rid.startswith("NFR-") and rtype != "NFR":
            errors.append(f"{label}: req_id prefix disagrees with type={rtype!r}")

        for field in ("statement", "acceptance_criteria", "reasoning"):
            if not str(r.get(field, "")).strip():
                errors.append(f"{label}: {field} is empty")

        if "shall" not in str(r.get("statement", "")).lower():
            errors.append(f"{label}: statement contains no 'shall'")

        cites = r.get("source_chunk_ids") or []
        if isinstance(cites, str):
            cites = [c.strip() for c in re.split(r"[;,]", cites) if c.strip()]
        if not isinstance(cites, list):
            errors.append(f"{label}: source_chunk_ids must be an array")
            cites = []

        derived = r.get("derived")
        if not isinstance(derived, bool):
            errors.append(f"{label}: derived must be a boolean, got {derived!r}")
            derived = bool(derived)

        fabricated = [c for c in cites if c not in valid_chunk_ids]
        if fabricated:
            errors.append(
                f"{label}: cites chunk_id(s) not present in the supplied evidence: "
                f"{fabricated}"
            )
        # The integrity rule from the build spec: a requirement must be either
        # cited or explicitly flagged as inferred. Both-empty is unfalsifiable.
        real = [c for c in cites if c in valid_chunk_ids]
        if not real and not derived:
            errors.append(f"{label}: no valid source_chunk_ids but derived=false")

        quote = str(r.get("evidence_quote", "") or "")

        records.append(
            {
                "req_id": rid,
                "type": rtype,
                "nfr_category": cat,
                "statement": str(r.get("statement", "")).strip(),
                "actor": r.get("actor"),
                "priority": r.get("priority"),
                "verification_method": r.get("verification_method"),
                "acceptance_criteria": str(r.get("acceptance_criteria", "")).strip(),
                "risk_class": r.get("risk_class"),
                "volatility": r.get("volatility"),
                "source_chunk_ids": ";".join(real),
                "derived": derived,
                "reasoning": str(r.get("reasoning", "")).strip(),
                "evidence_quote": quote.strip(),
                "inference_type": r.get("inference_type"),
                "_fabricated_chunk_ids": ";".join(fabricated),
            }
        )

    return records, errors


def traceability_matrix(records: list[dict[str, Any]], doc_ids: list[str]) -> pd.DataFrame:
    """Requirements x source documents. D = direct citation, I = inferred, blank = none."""
    rows = []
    for r in records:
        cites = [c for c in r["source_chunk_ids"].split(";") if c]
        docs = {c.split("#")[0] for c in cites}
        row = {"req_id": r["req_id"], "type": r["type"]}
        for d in doc_ids:
            row[d] = ("I" if r["derived"] else "D") if d in docs else ""
        rows.append(row)
    return pd.DataFrame(rows, columns=["req_id", "type", *doc_ids])


def generate(model_key: str = "primary", dry_run: bool = False) -> int:
    cfg = load_pipeline()
    out_dir = resolve(cfg["paths"]["outputs"])
    target = cfg["target"]
    gen = cfg["generation"]

    hits = retrieve_evidence()
    evidence, shown_ids = build_evidence(hits, cfg["retrieval"]["max_context_tokens"])

    print(
        f"[part1] retrieved {len(hits)} chunks "
        f"({cfg['retrieval'].get('strategy', 'single')} strategy), "
        f"{len(shown_ids)} fit the context budget"
    )
    by_doc: dict[str, int] = {}
    for cid in shown_ids:
        by_doc[cid.split("#")[0]] = by_doc.get(cid.split("#")[0], 0) + 1
    print(f"[part1] evidence spans: {dict(sorted(by_doc.items()))}")

    prompt = render(
        load_prompt("p1_requirements.txt"),
        TARGET_NAME=target["name"],
        TARGET_DESCRIPTION=target["description"].strip(),
        EVIDENCE=evidence,
        MIN_REQS=str(gen["min_requirements"]),
        MAX_REQS=str(gen["max_requirements"]),
        MIN_NFRS=str(gen["min_nfrs"]),
    )

    if dry_run:
        path = guard_write(out_dir / "_dry_run_p1_prompt.txt")
        path.write_text(prompt, encoding="utf-8")
        print(f"[part1] dry run — prompt ({len(prompt):,} chars) written to {path}")
        return 0

    client = OllamaClient()
    client.require([model_key])
    valid_ids = set(shown_ids)

    resp = client.generate(
        model_key,
        prompt=prompt,
        json_mode=True,
        tag="p1_requirements",
        meta={"target": target["id"]},
    )
    guard_write(out_dir / "raw_p1_response.txt").write_text(resp.text, encoding="utf-8")

    try:
        records, errors = validate_payload(resp.json(), valid_ids, cfg)
    except ValueError as exc:
        records, errors = [], [f"response was not parseable JSON: {exc}"]

    if errors:
        print(f"[part1] {len(errors)} contract violation(s); attempting one repair")
        for e in errors[:10]:
            print(f"        - {e}")

        repair = render(
            load_prompt("p1_repair.txt"),
            ERRORS="\n".join(f"- {e}" for e in errors),
            PREVIOUS=resp.text,
        )
        resp2 = client.generate(
            model_key,
            prompt=repair,
            json_mode=True,
            tag="p1_repair",
            meta={"target": target["id"], "repair_of": resp.call_id},
        )
        guard_write(out_dir / "raw_p1_repair_response.txt").write_text(
            resp2.text, encoding="utf-8"
        )
        try:
            records, errors = validate_payload(resp2.json(), valid_ids, cfg)
        except ValueError as exc:
            records, errors = [], [f"repair response was not parseable JSON: {exc}"]

        if errors:
            print(f"\n[part1] FAILED after repair — {len(errors)} violation(s) remain:")
            for e in errors:
                print(f"        - {e}")
            raise SystemExit(
                "Part 1 aborted. Raw responses are preserved in outputs/ and "
                "logs/llm_calls.jsonl for the report's failure analysis."
            )
        print("[part1] repair succeeded")

    df = pd.DataFrame(records)
    df[REQ_COLUMNS].to_csv(guard_write(out_dir / "requirements.csv"), index=False, encoding="utf-8")
    df[REASONING_COLUMNS].to_csv(
        guard_write(out_dir / "requirements_reasoning.csv"), index=False, encoding="utf-8"
    )

    doc_ids = sorted({c.split("#")[0] for r in records for c in r["source_chunk_ids"].split(";") if c})
    all_docs = sorted(set(doc_ids) | {f"D0{i}" for i in range(1, 7)})
    tm = traceability_matrix(records, all_docs)
    tm.to_csv(guard_write(out_dir / "traceability_matrix.csv"), index=False, encoding="utf-8")

    n_cited = sum(1 for r in records if r["source_chunk_ids"])
    rate = n_cited / len(records)
    n_nfr = sum(1 for r in records if r["type"] == "NFR")
    uncited_docs = [d for d in all_docs if not (tm[d] != "").any()]

    print(f"\n[part1] {len(records)} requirements ({len(records)-n_nfr} FR / {n_nfr} NFR)")
    print(f"[part1] traceability: {n_cited}/{len(records)} cite >=1 real chunk ({rate:.0%})")
    if rate < gen["min_traceability_rate"]:
        print(
            f"[part1] WARNING: below the {gen['min_traceability_rate']:.0%} target — "
            "report this rather than regenerating until it passes"
        )
    if uncited_docs:
        print(f"[part1] uncited source documents (a finding, not a bug): {uncited_docs}")
    print(f"[part1] wrote requirements.csv, requirements_reasoning.csv, traceability_matrix.csv")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Part 1 — requirement generation")
    ap.add_argument("--model", default="primary", choices=["primary", "secondary"])
    ap.add_argument("--dry-run", action="store_true", help="render the prompt without calling")
    args = ap.parse_args()
    try:
        return generate(args.model, args.dry_run)
    except LLMError as exc:
        print(f"[part1] FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
