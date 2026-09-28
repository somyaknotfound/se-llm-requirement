"""PART 1 driver — single-prompt requirement generation (the baseline).

    python -m src.generate_reqs
    python -m src.generate_reqs --case epcs_signing
    python -m src.generate_reqs --model secondary --dry-run

This is the non-agentic baseline the multi-agent system is compared against: one
prompt, document evidence only, no stakeholders, no clarification. With `--case` it
runs on that case study's functionality, facets and knowledge-source allowlist and
writes under outputs/cases/<id>/baseline/.

Contract enforcement is split three ways:

  * Unusable output is fatal after one repair: unparseable JSON, a broken schema,
    or a count outside the contract. Nothing downstream can run on it.

  * Citation integrity is recorded, not fatal. A chunk_id the model was never shown,
    or a requirement with no valid citation that claims not to be derived, is kept
    verbatim in `invalid_chunk_ids`, scored by the audit, and escalated for human
    review. Aborting on it meant the hallucination audit could never observe one.

  * Requirement QUALITY (weak words, compound obligations, unverifiable acceptance
    criteria) is not enforced here at all. validate.py measures it against
    ISO/IEC/IEEE 29148; repairing it at generation time would launder the output.
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
    "invalid_chunk_ids",
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


def repair_directive(payload: Any, cfg: dict[str, Any]) -> str:
    """Tell the repair prompt what kind of edit the errors actually require.

    A count shortfall is the one violation a repair cannot fix while obeying a
    blanket "do not add new requirements" rule. The first Colab run failed exactly
    here: the model returned 13 requirements, was told only that 18 were required,
    and dutifully returned the same 13 because the prompt forbade adding any.
    """
    gen = cfg["generation"]
    reqs = payload.get("requirements", []) if isinstance(payload, dict) else []
    n = len(reqs)
    n_nfr = sum(1 for r in reqs if isinstance(r, dict) and r.get("type") == "NFR")
    n_fr = n - n_nfr

    lines: list[str] = []
    if n < gen["min_requirements"]:
        need = gen["min_requirements"] - n
        lines.append(
            f"You returned {n} requirements but the contract requires at least "
            f"{gen['min_requirements']}. ADD {need} or more genuinely new requirements, "
            f"continuing the existing numbering. Keep every requirement you already "
            f"wrote exactly as it is. Draw the new ones from parts of the SOURCE "
            f"EVIDENCE above that you have not yet covered, and cite only chunk_ids "
            f"that appear in it. Do not pad the set with restatements of requirements "
            f"you have already written."
        )
    elif n > gen["max_requirements"]:
        lines.append(
            f"You returned {n} requirements but the contract allows at most "
            f"{gen['max_requirements']}. Merge or remove the weakest ones."
        )

    if n_fr < gen.get("min_frs", 0):
        lines.append(
            f"Only {n_fr} of your requirements are functional (type FR); at least "
            f"{gen['min_frs']} are required. The functionality has many distinct "
            f"functional steps — specify them as FRs rather than expressing "
            f"everything as a quality attribute."
        )
    if n_nfr < gen["min_nfrs"]:
        lines.append(
            f"Only {n_nfr} of your requirements are non-functional (type NFR); at "
            f"least {gen['min_nfrs']} are required."
        )

    if not lines:
        return (
            "Do not add new requirements and do not remove any — the set is the right "
            "size. Repair the fields the errors identify."
        )
    return "\n\n".join(lines)


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
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Check the model's JSON against the output contract.

    Returns (records, errors, flags). `errors` make the output unusable and are
    fatal after one repair. `flags` are per-requirement citation-integrity failures:
    the requirement is kept, the failure is recorded on it, and it is escalated.
    Requirement quality is out of scope here by design.
    """
    errors: list[str] = []
    flags: list[str] = []

    if not isinstance(payload, dict) or "requirements" not in payload:
        return [], ["top-level JSON must be an object with a 'requirements' array"], []
    reqs = payload["requirements"]
    if not isinstance(reqs, list) or not reqs:
        return [], ["'requirements' must be a non-empty array"], []

    gen = cfg["generation"]
    if not (gen["min_requirements"] <= len(reqs) <= gen["max_requirements"]):
        errors.append(
            f"produced {len(reqs)} requirements; contract requires between "
            f"{gen['min_requirements']} and {gen['max_requirements']}"
        )

    n_nfr = sum(1 for r in reqs if isinstance(r, dict) and r.get("type") == "NFR")
    if n_nfr < gen["min_nfrs"]:
        errors.append(f"only {n_nfr} NFRs; contract requires at least {gen['min_nfrs']}")

    n_fr = len(reqs) - n_nfr
    if n_fr < gen.get("min_frs", 0):
        errors.append(f"only {n_fr} FRs; contract requires at least {gen['min_frs']}")

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
        cites = [str(c).strip() for c in cites if str(c).strip()]

        derived = r.get("derived")
        if not isinstance(derived, bool):
            errors.append(f"{label}: derived must be a boolean, got {derived!r}")
            derived = bool(derived)

        real = [c for c in cites if c in valid_chunk_ids]
        invalid = [c for c in cites if c not in valid_chunk_ids]
        if invalid:
            flags.append(
                f"{label}: cites chunk_id(s) not present in the supplied evidence: {invalid}"
            )
        # A requirement must be either cited or explicitly flagged as inferred.
        # Both-empty is unfalsifiable.
        if not real and not derived:
            flags.append(f"{label}: no valid source_chunk_ids but derived=false")

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
                "invalid_chunk_ids": ";".join(invalid),
                "reasoning": str(r.get("reasoning", "")).strip(),
                "evidence_quote": str(r.get("evidence_quote", "") or "").strip(),
                "inference_type": r.get("inference_type"),
            }
        )

    return records, errors, flags


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


def _check(resp_text_json, valid_ids, cfg) -> tuple[Any, list[dict[str, Any]], list[str], list[str]]:
    payload: Any = {}
    try:
        payload = resp_text_json()
        records, errors, flags = validate_payload(payload, valid_ids, cfg)
    except ValueError as exc:
        records, errors, flags = [], [f"response was not parseable JSON: {exc}"], []
    return payload, records, errors, flags


def output_dir(case_id: str | None) -> Path:
    base = resolve(load_pipeline()["paths"]["outputs"])
    return base / "cases" / case_id / "baseline" if case_id else base


def generate(model_key: str = "primary", dry_run: bool = False, case_id: str | None = None) -> int:
    from .cases import load_case, target_for

    cfg = load_pipeline()
    out_dir = ensure_dir(output_dir(case_id))
    target = target_for(case_id)
    gen = cfg["generation"]

    facets = allowed = None
    if case_id:
        case = load_case(case_id)
        facets = case.get("facets")
        allowed = set(case.get("knowledge_sources", [])) or None

    hits = retrieve_evidence(facets=facets, allowed_docs=allowed)
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
        MIN_FRS=str(gen.get("min_frs", 0)),
    )

    if dry_run:
        path = guard_write(out_dir / "_dry_run_p1_prompt.txt")
        path.write_text(prompt, encoding="utf-8")
        print(f"[part1] dry run — prompt ({len(prompt):,} chars) written to {path}")
        return 0

    client = OllamaClient()
    client.require([model_key])
    valid_ids = set(shown_ids)
    # Both calls get a wider window than the pipeline default: 25 requirements with
    # per-requirement reasoning approach 6k tokens on their own, and the repair
    # prompt carries the evidence AND the previous response.
    window = {"num_ctx": gen.get("num_ctx", 32768), "num_predict": gen.get("num_predict", 8192)}

    resp = client.generate(
        model_key,
        prompt=prompt,
        json_mode=True,
        tag="p1_requirements",
        meta={"target": target["id"]},
        **window,
    )
    guard_write(out_dir / "raw_p1_response.txt").write_text(resp.text, encoding="utf-8")
    payload, records, errors, flags = _check(resp.json, valid_ids, cfg)
    contract: dict[str, Any] = {
        "initial_errors": errors,
        "initial_flags": flags,
        "repair_attempted": False,
        "used": "initial",
    }

    if errors or flags:
        print(f"[part1] {len(errors)} contract violation(s), {len(flags)} citation flag(s); "
              "attempting one repair")
        for e in (errors + flags)[:10]:
            print(f"        - {e}")

        directive = repair_directive(payload, cfg)
        print(f"[part1] repair directive: {directive.splitlines()[0][:96]}...")
        repair = render(
            load_prompt("p1_repair.txt"),
            ERRORS="\n".join(f"- {e}" for e in errors + flags),
            PREVIOUS=resp.text,
            DIRECTIVE=directive,
            EVIDENCE=evidence,
        )
        resp2 = client.generate(
            model_key,
            prompt=repair,
            json_mode=True,
            tag="p1_repair",
            meta={"target": target["id"], "repair_of": resp.call_id},
            **window,
        )
        guard_write(out_dir / "raw_p1_repair_response.txt").write_text(
            resp2.text, encoding="utf-8"
        )
        _, records2, errors2, flags2 = _check(resp2.json, valid_ids, cfg)
        contract.update(repair_attempted=True, repair_errors=errors2, repair_flags=flags2)

        # Use the repair when it produced usable output. If it broke something the
        # first response had right, fall back to the first response rather than
        # discarding a usable set; if neither is usable, abort.
        if not errors2:
            records, errors, flags = records2, errors2, flags2
            contract["used"] = "repair"
        elif errors:
            print(f"\n[part1] FAILED after repair — {len(errors2)} violation(s) remain:")
            for e in errors2:
                print(f"        - {e}")
            guard_write(out_dir / "part1_contract.json").write_text(
                json.dumps(contract, indent=2), encoding="utf-8"
            )
            raise SystemExit(
                "Part 1 aborted. Raw responses are preserved in outputs/ and "
                "logs/llm_calls.jsonl for the report's failure analysis."
            )
        else:
            print("[part1] the repair broke the contract; keeping the first response")
            contract["used"] = "initial_after_failed_repair"
        print(f"[part1] using the {contract['used']} response")

    contract["final_flags"] = flags
    guard_write(out_dir / "part1_contract.json").write_text(
        json.dumps(contract, indent=2), encoding="utf-8"
    )

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
    if flags:
        print(f"[part1] {len(flags)} citation-integrity flag(s) kept and escalated for review:")
        for f in flags:
            print(f"        - {f}")
    if rate < gen["min_traceability_rate"]:
        print(
            f"[part1] WARNING: below the {gen['min_traceability_rate']:.0%} target — "
            "report this rather than regenerating until it passes"
        )
    if uncited_docs:
        print(f"[part1] uncited source documents (a finding, not a bug): {uncited_docs}")
    print(f"[part1] wrote requirements.csv, requirements_reasoning.csv, traceability_matrix.csv "
          f"-> {out_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Part 1 — single-prompt requirement generation")
    ap.add_argument("--model", default="primary", choices=["primary", "secondary"])
    ap.add_argument("--case", default=None, help="run on a case study's functionality")
    ap.add_argument("--dry-run", action="store_true", help="render the prompt without calling")
    args = ap.parse_args()
    try:
        return generate(args.model, args.dry_run, args.case)
    except LLMError as exc:
        print(f"[part1] FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
