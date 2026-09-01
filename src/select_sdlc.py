"""PART 2 driver — SDLC model selection under three framings, two models, three trials.

    python -m src.select_sdlc
    python -m src.select_sdlc --dry-run --framing plan_primed

The model is shown ONLY the requirement artifact (statement, type, priority,
risk_class, volatility). requirements_reasoning.csv is deliberately withheld: if
the model were handed back its own Part 1 narrative it would be re-reading its
prior justification rather than reasoning from the specification, and the
grounding measurement would be meaningless.

Trials vary the SEED, not the temperature. At temperature 0.1 with a fixed seed
every trial would be byte-identical and the stability analysis would measure
nothing; raising the temperature instead would confound sampling noise with
framing sensitivity. Holding temperature fixed and stepping the seed isolates
sampling variance, which is the quantity the report actually needs.
"""

from __future__ import annotations

import argparse
import re
from typing import Any

import pandas as pd

from . import load_pipeline, resolve
from .generate_reqs import guard_write, load_prompt, render
from .llm import LLMError, OllamaClient

FRAMING_PROMPTS = {
    "neutral": ("R1", "p2_sdlc_neutral.txt"),
    "agile_primed": ("R2", "p2_sdlc_agile_primed.txt"),
    "plan_primed": ("R3", "p2_sdlc_plan_primed.txt"),
}

ANALYSIS_COLUMNS = [
    "run_id",
    "model",
    "framing",
    "trial",
    "recommended_sdlc",
    "runner_up",
    "criterion",
    "score",
    "criterion_justification",
    "cited_req_ids",
]

RUN_COLUMNS = [
    "run_id",
    "model",
    "model_id",
    "framing",
    "trial",
    "seed",
    "recommended_sdlc",
    "recommended_canonical",
    "runner_up",
    "runner_up_canonical",
    "overall_justification",
    "strongest_counterargument",
    "latency_s",
    "status",
]

# Canonical families for agreement and flip-rate arithmetic. Free-text model names
# ("Scrum", "Agile/Scrum", "agile with sprints") are the same recommendation and
# must not be counted as three different answers; conversely a hybrid that wraps
# iterative delivery in a verification gate is a genuinely distinct position and
# keeps its own family.
_CANONICAL_PATTERNS: list[tuple[str, str]] = [
    (r"hybrid|wrapper|within a|combined|v-model.*agile|agile.*v-model", "Hybrid"),
    (r"\bv[- ]?model\b|verification and validation model", "V-Model"),
    (r"spiral", "Spiral"),
    (r"waterfall", "Waterfall"),
    (r"incremental|iterative", "Incremental/Iterative"),
    (r"agile|scrum|kanban|xp\b|extreme programming|safe\b", "Agile"),
    (r"\brad\b|rapid application", "RAD"),
    (r"prototyp", "Prototyping"),
    (r"devops|continuous delivery", "DevOps"),
]


def canonical_sdlc(name: str) -> str:
    text = (name or "").strip().lower()
    if not text:
        return "unknown"
    for pattern, family in _CANONICAL_PATTERNS:
        if re.search(pattern, text):
            return family
    return name.strip()


def render_requirements(df: pd.DataFrame) -> str:
    """The artifact handed to Part 2 — statements plus the four decision-relevant fields."""
    lines = [
        "req_id | type | priority | risk_class | volatility | statement",
        "-------|------|----------|------------|------------|----------",
    ]
    for _, r in df.iterrows():
        statement = " ".join(str(r["statement"]).split())
        lines.append(
            f"{r['req_id']} | {r['type']} | {r['priority']} | "
            f"{r['risk_class']} | {r['volatility']} | {statement}"
        )
    return "\n".join(lines)


def parse_run(payload: Any, criteria: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {}, [], ["response was not a JSON object"]

    header = {
        "recommended_sdlc": str(payload.get("recommended_sdlc", "")).strip(),
        "runner_up": str(payload.get("runner_up", "")).strip(),
        "overall_justification": str(payload.get("overall_justification", "")).strip(),
        "strongest_counterargument": str(payload.get("strongest_counterargument", "")).strip(),
    }
    if not header["recommended_sdlc"]:
        errors.append("recommended_sdlc is empty")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload.get("criteria", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("criterion", "")).strip()
        if name not in criteria:
            errors.append(f"unknown criterion {name!r}")
            continue
        seen.add(name)
        try:
            score = int(item.get("score"))
        except (TypeError, ValueError):
            score = None
            errors.append(f"{name}: score {item.get('score')!r} is not an integer")
        if score is not None and not 1 <= score <= 5:
            errors.append(f"{name}: score {score} outside 1-5")

        cites = item.get("cited_req_ids") or []
        if isinstance(cites, str):
            cites = [c.strip() for c in re.split(r"[;,]", cites) if c.strip()]
        rows.append(
            {
                "criterion": name,
                "score": score,
                "criterion_justification": " ".join(
                    str(item.get("justification", "")).split()
                ),
                "cited_req_ids": ";".join(str(c).strip() for c in cites),
            }
        )

    for missing in [c for c in criteria if c not in seen]:
        errors.append(f"missing criterion {missing}")

    return header, rows, errors


def run_matrix(dry_run: bool = False, only_framing: str | None = None) -> int:
    cfg = load_pipeline()
    out_dir = resolve(cfg["paths"]["outputs"])
    target = cfg["target"]
    sdlc_cfg = cfg["sdlc"]
    criteria = sdlc_cfg["criteria"]

    req_path = out_dir / "requirements.csv"
    if not req_path.exists():
        raise SystemExit(
            f"{req_path} missing — run `python -m src.generate_reqs` before Part 2."
        )
    reqs = pd.read_csv(req_path)
    requirements_block = render_requirements(reqs)
    print(f"[part2] feeding {len(reqs)} requirements (reasoning withheld)")

    framings = [only_framing] if only_framing else sdlc_cfg["framings"]

    if dry_run:
        framing = framings[0]
        _, prompt_file = FRAMING_PROMPTS[framing]
        prompt = render(
            load_prompt(prompt_file),
            TARGET_NAME=target["name"],
            TARGET_DESCRIPTION=target["description"].strip(),
            REQUIREMENTS=requirements_block,
        )
        path = guard_write(out_dir / f"_dry_run_p2_{framing}_prompt.txt")
        path.write_text(prompt, encoding="utf-8")
        print(f"[part2] dry run — {framing} prompt ({len(prompt):,} chars) -> {path}")
        return 0

    client = OllamaClient()
    client.require(sdlc_cfg["models"])

    analysis_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    total = len(framings) * len(sdlc_cfg["models"]) * sdlc_cfg["trials"]
    done = 0

    for framing in framings:
        run_id, prompt_file = FRAMING_PROMPTS[framing]
        prompt = render(
            load_prompt(prompt_file),
            TARGET_NAME=target["name"],
            TARGET_DESCRIPTION=target["description"].strip(),
            REQUIREMENTS=requirements_block,
        )

        for model_key in sdlc_cfg["models"]:
            base_seed = client.resolve_model(model_key)[1].get("seed", 42)
            for trial in range(1, sdlc_cfg["trials"] + 1):
                done += 1
                seed = base_seed + trial
                label = f"{run_id}/{model_key}/t{trial}"
                print(f"[part2] {done}/{total} {label} (seed={seed}) ...", flush=True)

                status = "ok"
                header: dict[str, Any] = {}
                rows: list[dict[str, Any]] = []
                latency = None
                model_id = client.resolve_model(model_key)[0]

                try:
                    resp = client.generate(
                        model_key,
                        prompt=prompt,
                        json_mode=True,
                        tag="p2_sdlc",
                        meta={
                            "run_id": run_id,
                            "framing": framing,
                            "trial": trial,
                            "seed": seed,
                        },
                        seed=seed,
                    )
                    latency = resp.latency_s
                    header, rows, errors = parse_run(resp.json(), criteria)
                    if errors:
                        # A malformed run is recorded, not retried. Silently
                        # re-rolling until the output parses would bias the very
                        # stability statistic this matrix exists to measure.
                        status = "partial: " + "; ".join(errors[:3])
                        print(f"          {len(errors)} issue(s): {errors[0]}")
                except (LLMError, ValueError) as exc:
                    status = f"failed: {type(exc).__name__}: {exc}"
                    print(f"          FAILED: {exc}")

                rec = header.get("recommended_sdlc", "")
                run_rows.append(
                    {
                        "run_id": run_id,
                        "model": model_key,
                        "model_id": model_id,
                        "framing": framing,
                        "trial": trial,
                        "seed": seed,
                        "recommended_sdlc": rec,
                        "recommended_canonical": canonical_sdlc(rec),
                        "runner_up": header.get("runner_up", ""),
                        "runner_up_canonical": canonical_sdlc(header.get("runner_up", "")),
                        "overall_justification": " ".join(
                            header.get("overall_justification", "").split()
                        ),
                        "strongest_counterargument": " ".join(
                            header.get("strongest_counterargument", "").split()
                        ),
                        "latency_s": latency,
                        "status": status,
                    }
                )
                for row in rows:
                    analysis_rows.append(
                        {
                            "run_id": run_id,
                            "model": model_key,
                            "framing": framing,
                            "trial": trial,
                            "recommended_sdlc": rec,
                            "runner_up": header.get("runner_up", ""),
                            **row,
                        }
                    )
                if rec:
                    print(f"          -> {rec}  (canonical: {canonical_sdlc(rec)})")

    pd.DataFrame(analysis_rows, columns=ANALYSIS_COLUMNS).to_csv(
        guard_write(out_dir / "sdlc_analysis.csv"), index=False, encoding="utf-8"
    )
    pd.DataFrame(run_rows, columns=RUN_COLUMNS).to_csv(
        guard_write(out_dir / "sdlc_runs.csv"), index=False, encoding="utf-8"
    )

    ok = [r for r in run_rows if r["recommended_canonical"] != "unknown"]
    print(f"\n[part2] {len(run_rows)} runs, {len(ok)} produced a recommendation")
    if ok:
        counts = pd.Series([r["recommended_canonical"] for r in ok]).value_counts()
        print("[part2] recommendation distribution:")
        for name, n in counts.items():
            print(f"          {name:<22} {n:>2}/{len(ok)}")
        for framing in framings:
            sub = [r["recommended_canonical"] for r in ok if r["framing"] == framing]
            if sub:
                print(f"[part2] {framing:<14} -> {pd.Series(sub).value_counts().to_dict()}")
    print("[part2] wrote sdlc_analysis.csv, sdlc_runs.csv")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Part 2 — SDLC selection matrix")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--framing", choices=list(FRAMING_PROMPTS), default=None)
    args = ap.parse_args()
    try:
        return run_matrix(args.dry_run, args.framing)
    except LLMError as exc:
        print(f"[part2] FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
