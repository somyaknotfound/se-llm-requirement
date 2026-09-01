"""Metrics summary across every stage.

    python -m src.metrics

Reads whatever outputs exist and skips the rest, so it can be run mid-build to see
where the pipeline stands. Every metric is written to outputs/metrics_summary.csv
as (section, metric, value, detail) so the report can cite a number without
recomputing it in prose — recomputed-by-hand figures are how reports end up
contradicting their own appendices.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import load_pipeline, resolve
from .generate_reqs import guard_write

DOC_IDS = [f"D0{i}" for i in range(1, 7)]


def _rows(section: str, pairs: list[tuple[str, Any, str]]) -> list[dict[str, Any]]:
    return [{"section": section, "metric": m, "value": v, "detail": d} for m, v, d in pairs]


def corpus_metrics(cfg: dict) -> list[dict[str, Any]]:
    manifest_path = resolve(cfg["paths"]["manifest"])
    chunks_path = resolve(cfg["paths"]["chunks"])
    if not manifest_path.exists():
        return []
    man = pd.read_csv(manifest_path)
    out = [
        ("source_documents", len(man), "; ".join(man["doc_id"].astype(str))),
        ("corpus_bytes", int(man["bytes"].fillna(0).sum()), "raw downloaded bytes"),
    ]
    if chunks_path.exists():
        with chunks_path.open(encoding="utf-8") as fh:
            chunks = [json.loads(l) for l in fh if l.strip()]
        tokens = sum(c["token_count"] for c in chunks)
        out += [
            ("chunks", len(chunks), f"tokenizer={cfg['chunking']['tokenizer']}"),
            ("chunk_tokens_total", tokens, ""),
            ("chunk_tokens_mean", round(tokens / max(1, len(chunks)), 1), ""),
        ]
    return _rows("corpus", out)


def part1_metrics(out_dir: Path, cfg: dict) -> list[dict[str, Any]]:
    path = out_dir / "requirements.csv"
    if not path.exists():
        return []
    reqs = pd.read_csv(path).fillna("")
    n = len(reqs)
    n_nfr = int((reqs["type"] == "NFR").sum())
    cited = reqs["source_chunk_ids"].astype(str).str.strip().ne("")
    derived = reqs["derived"].astype(str).str.lower().isin(["true", "1", "yes"])

    docs_seen: set[str] = set()
    for val in reqs["source_chunk_ids"].astype(str):
        for c in val.split(";"):
            if c.strip():
                docs_seen.add(c.split("#")[0])
    uncited = [d for d in DOC_IDS if d not in docs_seen]

    integrity_bugs = int((~cited & ~derived).sum())

    out = [
        ("requirements_total", n, ""),
        ("requirements_fr", n - n_nfr, ""),
        ("requirements_nfr", n_nfr, f"target >= {cfg['generation']['min_nfrs']}"),
        ("traceability_rate", round(cited.mean(), 3) if n else 0,
         f"share citing >=1 chunk_id; target >= {cfg['generation']['min_traceability_rate']}"),
        ("derived_rate", round(derived.mean(), 3) if n else 0, "share marked derived=true"),
        ("documents_cited", len(docs_seen), "; ".join(sorted(docs_seen))),
        ("documents_uncited", len(uncited), "; ".join(uncited) or "none"),
        ("integrity_violations", integrity_bugs,
         "rows with no citation AND derived=false (must be 0)"),
    ]
    if "nfr_category" in reqs:
        cats = reqs.loc[reqs["type"] == "NFR", "nfr_category"].value_counts().to_dict()
        out.append(("nfr_categories", len(cats), str(cats)))
    for col in ("risk_class", "volatility", "priority"):
        if col in reqs:
            out.append((f"{col}_distribution", "", str(reqs[col].value_counts().to_dict())))
    return _rows("part1", out)


def validation_metrics(out_dir: Path) -> list[dict[str, Any]]:
    path = out_dir / "validation_29148.csv"
    if not path.exists():
        return []
    val = pd.read_csv(path)
    out: list[tuple[str, Any, str]] = []

    for attr, grp in val.groupby("attribute"):
        rule = grp["rule_score"].mean()
        llm = grp["llm_score"].mean() if grp["llm_score"].notna().any() else None
        detail = f"rule={rule:.0%}" + (f", llm={llm:.0%}" if llm is not None else ", llm=n/a")
        out.append((f"pass_rate_{attr}", round(rule, 3), detail))

    scored = val[val["agreement"].isin(["agree", "disagree"])]
    if len(scored):
        out.append((
            "scorer_agreement",
            round((scored["agreement"] == "agree").mean(), 3),
            f"{len(scored)} judgements compared",
        ))
        by_attr = (
            scored.assign(a=scored["agreement"].eq("agree"))
            .groupby("attribute")["a"].mean().round(2).to_dict()
        )
        out.append(("scorer_agreement_by_attribute", "", str(by_attr)))
        out.append(("disagreements", int((scored["agreement"] == "disagree").sum()), ""))
    else:
        out.append(("scorer_agreement", "n/a", "LLM critic did not run"))

    adjudicated = val[val["human_adjudication"].astype(str).str.strip().ne("")]
    out.append(("human_adjudicated", len(adjudicated), "conflicts resolved by hand"))
    return _rows("validation", out)


def hallucination_metrics(out_dir: Path) -> list[dict[str, Any]]:
    path = out_dir / "hallucination_audit.csv"
    if not path.exists():
        return []
    aud = pd.read_csv(path)
    if aud.empty:
        return _rows("hallucination", [("citations_checked", 0, "")])
    counts = aud["verdict"].value_counts().to_dict()
    bad = int(aud["verdict"].isin(["fabricated", "misattributed"]).sum())
    out = [
        ("citations_checked", len(aud), str(counts)),
        ("fabricated", int(counts.get("fabricated", 0)), ""),
        ("misattributed", int(counts.get("misattributed", 0)), ""),
        ("unverifiable", int(counts.get("unverifiable", 0)), ""),
        ("hallucination_rate", round(bad / len(aud), 3),
         "(fabricated + misattributed) / citations checked"),
        ("high_severity", int((aud["severity"] == "high").sum()),
         "fabricated citation on a safety-critical requirement"),
    ]
    by_type = aud.groupby("entity_type")["verdict"].apply(
        lambda s: s.isin(["fabricated", "misattributed"]).sum()
    ).to_dict()
    out.append(("suspect_by_entity_type", "", str(by_type)))
    return _rows("hallucination", out)


def part2_metrics(out_dir: Path) -> list[dict[str, Any]]:
    runs_path = out_dir / "sdlc_runs.csv"
    analysis_path = out_dir / "sdlc_analysis.csv"
    if not runs_path.exists():
        return []
    runs = pd.read_csv(runs_path).fillna("")
    ok = runs[runs["recommended_canonical"].ne("") & runs["recommended_canonical"].ne("unknown")]
    if ok.empty:
        return _rows("part2", [("runs", len(runs), "no run produced a recommendation")])

    modal = ok["recommended_canonical"].mode().iloc[0]
    modal_share = (ok["recommended_canonical"] == modal).mean()

    # Framing sensitivity: hold model and trial fixed, vary framing. If the
    # recommendation is stable the set collapses to one value.
    flips = 0
    groups = 0
    for _, grp in ok.groupby(["model", "trial"]):
        if len(grp) > 1:
            groups += 1
            flips += int(grp["recommended_canonical"].nunique() > 1)

    # Cross-model agreement: hold framing and trial fixed, vary model.
    agree = 0
    pairs = 0
    for _, grp in ok.groupby(["framing", "trial"]):
        if grp["model"].nunique() > 1:
            pairs += 1
            agree += int(grp["recommended_canonical"].nunique() == 1)

    out: list[tuple[str, Any, str]] = [
        ("runs_total", len(runs), ""),
        ("runs_with_recommendation", len(ok), ""),
        ("modal_recommendation", modal, str(ok["recommended_canonical"].value_counts().to_dict())),
        ("modal_share", round(modal_share, 3), "share of runs choosing the modal model"),
        ("framing_flip_rate", round(flips / groups, 3) if groups else "n/a",
         f"{flips}/{groups} (model,trial) groups changed answer across framings"),
        ("cross_model_agreement", round(agree / pairs, 3) if pairs else "n/a",
         f"{agree}/{pairs} (framing,trial) pairs where both models agreed"),
    ]
    for framing, grp in ok.groupby("framing"):
        out.append((f"recommendation_{framing}", "", str(grp["recommended_canonical"].value_counts().to_dict())))

    if analysis_path.exists():
        an = pd.read_csv(analysis_path).fillna("")
        if len(an):
            grounded = an["cited_req_ids"].astype(str).str.strip().ne("")
            out.append((
                "grounding_rate",
                round(grounded.mean(), 3),
                "criterion justifications citing >=1 req_id vs generic SE reasoning",
            ))
            reqs_path = out_dir / "requirements.csv"
            if reqs_path.exists():
                valid = set(pd.read_csv(reqs_path)["req_id"].astype(str))
                def all_real(cell: str) -> bool:
                    ids = [c.strip() for c in str(cell).split(";") if c.strip()]
                    return bool(ids) and all(i in valid for i in ids)
                out.append((
                    "grounding_rate_valid_ids",
                    round(an["cited_req_ids"].apply(all_real).mean(), 3),
                    "justifications where every cited req_id actually exists",
                ))
            means = an.groupby("criterion")["score"].mean().round(2).to_dict()
            out.append(("criterion_mean_scores", "", str(means)))
    return _rows("part2", out)


def cost_metrics(cfg: dict) -> list[dict[str, Any]]:
    log_path = resolve(cfg["paths"]["logs"])
    if not log_path.exists():
        return []
    calls, prompt_tok, completion_tok, wall, errors = 0, 0, 0, 0.0, 0
    by_tag: dict[str, int] = {}
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") == "generate_error":
            errors += 1
            continue
        if rec.get("event") != "generate":
            continue
        calls += 1
        prompt_tok += rec.get("prompt_tokens") or 0
        completion_tok += rec.get("completion_tokens") or 0
        wall += rec.get("latency_s") or 0.0
        tag = rec.get("tag") or "untagged"
        by_tag[tag] = by_tag.get(tag, 0) + 1
    return _rows("cost", [
        ("llm_calls", calls, str(by_tag)),
        ("llm_call_errors", errors, "failed attempts (retried)"),
        ("prompt_tokens_total", prompt_tok, ""),
        ("completion_tokens_total", completion_tok, ""),
        ("tokens_total", prompt_tok + completion_tok, ""),
        ("wall_clock_s", round(wall, 1), f"{round(wall/60, 1)} minutes of model time"),
    ])


def main() -> int:
    cfg = load_pipeline()
    out_dir = resolve(cfg["paths"]["outputs"])

    rows: list[dict[str, Any]] = []
    rows += corpus_metrics(cfg)
    rows += part1_metrics(out_dir, cfg)
    rows += validation_metrics(out_dir)
    rows += hallucination_metrics(out_dir)
    rows += part2_metrics(out_dir)
    rows += cost_metrics(cfg)

    if not rows:
        print("[metrics] nothing to summarise yet — run the pipeline stages first")
        return 0

    # dtype=object keeps counts as ints. Without it, a stage whose metrics happen
    # to be all-numeric upcasts the column to float64 and the report reads
    # "6.0 source documents".
    df = pd.DataFrame(rows, columns=["section", "metric", "value", "detail"], dtype=object)
    df.to_csv(guard_write(out_dir / "metrics_summary.csv"), index=False, encoding="utf-8")

    section = None
    for _, r in df.iterrows():
        if r["section"] != section:
            section = r["section"]
            print(f"\n== {section} ==")
        val = r["value"]
        print(f"  {r['metric']:<32} {str(val):<12} {str(r['detail'])[:58]}")
    print(f"\n[metrics] wrote {out_dir / 'metrics_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
