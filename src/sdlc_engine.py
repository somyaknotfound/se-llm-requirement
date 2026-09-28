"""SDLC selection engine: deterministic rules + MCDA, then a tailored workflow.

    python -m src.sdlc_engine --scores '{"regulatory_criticality": 5, ...}'
    python -m src.sdlc_engine --consistency        # Part 2 matrix: LLM pick vs engine pick

The LLM's job in SDLC selection is perception: score the brief's 13 decision
factors from the requirement set and project context, citing requirement ids. The
decision itself is made here, deterministically, from config/sdlc.yaml:

  * MCDA — simple additive weighting over directional profiles gives every model a
    suitability percentage, so the output is a ranking, not a single label.
  * Rules — the brief's condition table, transcribed; a fired rule is auditable
    support for a model.
  * Cautions — known failure modes of a top pick (an adaptive model on a regulated,
    safety-critical project; a plan-driven model under high change).

When the top model has no supporting rule, carries a caution, or leads by a narrow
margin, the recommendation is escalated: SDLC adoption is a human decision.

Separating perception from decision is also what makes the model's own reasoning
checkable: if its free-text recommendation disagrees with what its own factor
scores imply, that inconsistency is a finding.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from functools import lru_cache
from typing import Any

import yaml

from . import resolve

_COND = re.compile(r"^\s*([a-z_]+)\s*(<=|>=|<|>|==)\s*(\d+(?:\.\d+)?)\s*$")


@lru_cache(maxsize=1)
def load_sdlc() -> dict[str, Any]:
    return yaml.safe_load((resolve("config") / "sdlc.yaml").read_text(encoding="utf-8"))


def factor_names() -> list[str]:
    return list(load_sdlc()["factors"])


def evaluate(cond: Any, scores: dict[str, float]) -> bool:
    """Evaluate a rule condition: 'factor >= 4', or {'all': [...]} / {'any': [...]}."""
    if isinstance(cond, dict):
        if "all" in cond:
            return all(evaluate(c, scores) for c in cond["all"])
        if "any" in cond:
            return any(evaluate(c, scores) for c in cond["any"])
        raise ValueError(f"condition must have 'all' or 'any': {cond}")
    m = _COND.match(str(cond))
    if not m:
        raise ValueError(f"unparseable condition {cond!r}")
    factor, op, value = m.group(1), m.group(2), float(m.group(3))
    if factor not in scores:
        return False
    s = float(scores[factor])
    return {"<=": s <= value, ">=": s >= value, "<": s < value, ">": s > value, "==": s == value}[op]


def suitability(scores: dict[str, float]) -> list[dict[str, Any]]:
    """Weighted mean directional fit per model, as a percentage, best first."""
    cfg = load_sdlc()
    weights = cfg.get("weights") or {}
    ranking = []
    for model, profile in cfg["profiles"].items():
        num = den = 0.0
        contributions: dict[str, float] = {}
        for factor, spec in profile.items():
            if factor not in scores:
                continue
            s = min(5.0, max(1.0, float(scores[factor])))
            fit = (s - 1) / 4 if int(spec["dir"]) > 0 else (5 - s) / 4
            w = float(weights.get(factor, 1.0))
            num += w * fit
            den += w
            contributions[factor] = round(fit, 3)
        pct = round(100 * num / den, 1) if den else 0.0
        ranking.append({"model": model, "pct": pct, "contributions": contributions})
    ranking.sort(key=lambda r: -r["pct"])
    return ranking


def fired_rules(scores: dict[str, float]) -> list[dict[str, Any]]:
    return [
        {"id": r["id"], "model": r["model"], "brief_condition": r["brief_condition"]}
        for r in load_sdlc()["rules"]
        if evaluate(r["when"], scores)
    ]


def recommend(scores: dict[str, float], margin: float = 5.0) -> dict[str, Any]:
    cfg = load_sdlc()
    ranking = suitability(scores)
    rules = fired_rules(scores)
    support: dict[str, list[str]] = {}
    for r in rules:
        support.setdefault(r["model"], []).append(r["id"])
    for entry in ranking:
        entry["rule_support"] = support.get(entry["model"], [])

    top, runner = ranking[0], ranking[1]
    cautions = [
        c["text"].strip()
        for c in cfg.get("cautions", [])
        if top["model"] in c["models"] and evaluate(c["when"], scores)
    ]
    reasons: list[str] = []
    if not top["rule_support"]:
        reasons.append(f"no brief rule supports the top-ranked model ({top['model']})")
    if cautions:
        reasons.append("caution raised for the top-ranked model")
    if top["pct"] - runner["pct"] < margin:
        reasons.append(f"near tie: {top['model']} {top['pct']}% vs {runner['model']} {runner['pct']}%")

    return {
        "top": top["model"],
        "runner_up": runner["model"],
        "ranking": ranking,
        "fired_rules": rules,
        "cautions": cautions,
        "escalate": bool(reasons),
        "escalation_reasons": reasons,
        "scores": scores,
    }


def aggregate(score_sets: list[dict[str, Any]]) -> dict[str, float]:
    """Median score per factor across several scorings (models, trials)."""
    out: dict[str, float] = {}
    for factor in factor_names():
        vals = [float(s[factor]) for s in score_sets if isinstance(s.get(factor), (int, float))]
        if vals:
            out[factor] = float(statistics.median(vals))
    return out


# --- workflow generation --------------------------------------------------


def build_workflow(
    model: str,
    source_docs: set[str],
    safety_critical: bool,
    security_risk: float,
) -> list[dict[str, Any]]:
    """Instantiate the model's workflow template and apply the overlays.

    Overlays: security activities scaled by the security-risk factor, compliance
    checkpoints for each regulatory source the requirements trace to, clinical
    safety activities when any requirement is safety-critical, human approval gates,
    and a traceability check at every gate.
    """
    cfg = load_sdlc()
    ov = cfg["overlays"]
    # Copy the list fields: the template is cached config and must not be mutated.
    phases = [
        dict(p, activities=list(p.get("activities", [])), security=[], checkpoints=[], gate=[])
        for p in cfg["workflows"][model]
    ]

    def attach(kind: str, key: str, items: list[str]) -> None:
        for p in phases:
            if p["kind"] == kind:
                p[key].extend(items)
                return

    if security_risk >= 3:
        for kind, items in ov["security"].items():
            attach(kind, "security", items if security_risk >= 4 else items[:1])

    for doc in sorted(source_docs):
        for cp in ov["compliance_by_source"].get(doc, []):
            attach(cp["kind"], "checkpoints", [cp["checkpoint"]])

    if safety_critical:
        for kind, items in ov["clinical_safety"].items():
            attach(kind, "activities", items)

    for kind, roles in ov["gates"].items():
        for p in phases:
            if p["kind"] == kind and not p["gate"]:
                p["gate"] = list(roles)
                p["traceability"] = ov["traceability"]
                break
    return phases


def workflow_markdown(model: str, phases: list[dict[str, Any]]) -> str:
    lines = [f"## Project workflow — {model}", "",
             "| # | Phase | Activities | Roles | Deliverables | Security | Compliance checkpoints | Exit criterion | Approval gate |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(phases, start=1):
        cells = [
            str(i), p["name"], "; ".join(p.get("activities", [])), ", ".join(p.get("roles", [])),
            "; ".join(p.get("deliverables", [])), "; ".join(p.get("security", [])),
            "; ".join(p.get("checkpoints", [])), p.get("exit", ""),
            ", ".join(p.get("gate", [])) + (" (RTM checked)" if p.get("traceability") else ""),
        ]
        lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    return "\n".join(lines)


def workflow_mermaid(phases: list[dict[str, Any]]) -> str:
    lines = ["flowchart LR"]
    for i, p in enumerate(phases):
        label = p["name"].replace('"', "'")
        shape = f'P{i}{{{{"{label}"}}}}' if p.get("gate") else f'P{i}["{label}"]'
        lines.append(f"    {shape}")
        if i:
            lines.append(f"    P{i-1} --> P{i}")
    return "\n".join(lines)


# --- Part 2 consistency check ---------------------------------------------


def consistency_report() -> list[dict[str, Any]]:
    """For each Part 2 run: does the model's own pick match what its scores imply?"""
    import pandas as pd

    from . import load_pipeline
    from .select_sdlc import canonical_sdlc

    out_dir = resolve(load_pipeline()["paths"]["outputs"])
    an_path = out_dir / "sdlc_analysis.csv"
    if not an_path.exists():
        raise SystemExit(f"{an_path} missing — run python -m src.select_sdlc first")
    an = pd.read_csv(an_path)
    rows = []
    for (run_id, model, framing, trial), grp in an.groupby(["run_id", "model", "framing", "trial"]):
        scores = {r["criterion"]: r["score"] for _, r in grp.iterrows() if pd.notna(r["score"])}
        if len(scores) < len(factor_names()) // 2:
            continue
        rec = recommend(scores)
        llm = canonical_sdlc(str(grp["recommended_sdlc"].iloc[0]))
        rows.append({
            "run_id": run_id, "model": model, "framing": framing, "trial": trial,
            "llm_recommendation": llm, "engine_top": rec["top"],
            "engine_top_pct": rec["ranking"][0]["pct"], "engine_runner_up": rec["runner_up"],
            "consistent": llm == rec["top"],
            "fired_rules": ";".join(r["id"] for r in rec["fired_rules"]),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="SDLC rules + MCDA engine")
    ap.add_argument("--scores", help="JSON object of factor scores (1-5)")
    ap.add_argument("--consistency", action="store_true",
                    help="compare each Part 2 run's recommendation with its own scores' implication")
    args = ap.parse_args()

    if args.consistency:
        import pandas as pd

        from . import load_pipeline
        from .generate_reqs import guard_write

        rows = consistency_report()
        out = resolve(load_pipeline()["paths"]["outputs"]) / "sdlc_consistency.csv"
        pd.DataFrame(rows).to_csv(guard_write(out), index=False, encoding="utf-8")
        if rows:
            rate = sum(r["consistent"] for r in rows) / len(rows)
            print(f"[engine] {len(rows)} runs; LLM pick matches its own scores' implication in {rate:.0%}")
        print(f"[engine] wrote {out}")
        return 0

    if not args.scores:
        ap.error("pass --scores or --consistency")
    rec = recommend(json.loads(args.scores))
    for r in rec["ranking"]:
        rules = ",".join(r["rule_support"]) or "-"
        print(f"  {r['model']:<10} {r['pct']:>5.1f}%   rules: {rules}")
    for c in rec["cautions"]:
        print(f"  caution: {c}")
    if rec["escalate"]:
        print(f"  ESCALATE: {'; '.join(rec['escalation_reasons'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
