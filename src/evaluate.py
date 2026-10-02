"""Evaluation against the case gold standards (brief point 19).

    python -m src.evaluate --case all
    python -m src.evaluate --case erx_issuance --injection-replay

For each case it compares the multi-agent system with the single-prompt baseline
(src/generate_reqs.py --case <id>) on the same gold standard:

    extraction precision / recall / F1   one-to-one matching of generated to gold
                                         requirements by embedding similarity
    completeness                         = recall (share of gold requirements found)
    category agreement                   mean Jaccard of multi-label categories on matches
    ambiguity-detection recall           seeded vague facts the system followed up
    conflict-detection recall/precision  seeded conflicts flagged by the conflict agent
    regulatory-control coverage          applicable controls covered by >= 1 requirement
    citation correctness                 evidence quotes found verbatim in the cited chunk
    hallucination rate                   (fabricated + misattributed) / citations checked
    29148 quality                        mean rule pass rate, first draft and final
    traceability coverage                requirements traceable to a statement or chunk
    SDLC accuracy                        engine top-1 / top-2 against the expert choice
    human correction rate                (modify + reject) / decisions recorded
    processing time vs manual            pipeline minutes against the author's manual effort
    stakeholder satisfaction             SUS from the survey the web UI collects
    injection attack success             replay of each seeded injection with and without defences

Anything that needs a human — gold review, expert SDLC, manual effort, decisions,
survey responses — is reported as missing rather than estimated. Automatic matches
are written to a sheet with an empty `human_verdict` column; once it is filled, the
precision is recomputed from the verified matches.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from . import ensure_dir, load_pipeline, resolve
from .cases import case_ids, case_out_dir, load_case, load_gold
from .knowledge import applicable_controls, controls_by_id

SUS_ITEMS = 10


def _eval_dir() -> Path:
    return ensure_dir(resolve(load_pipeline()["paths"]["outputs"]) / "evaluation")


def _split(cell: Any) -> list[str]:
    return [c.strip() for c in str(cell or "").split(";") if c.strip() and c.strip() != "nan"]


def _embed(texts: list[str]):
    import numpy as np

    from .index import _embedder

    model = _embedder(load_pipeline()["retrieval"]["embedding_model"])
    return np.asarray(model.encode(texts, normalize_embeddings=True), dtype="float32")


def match(generated: list[dict[str, Any]], gold: list[dict[str, Any]], threshold: float,
          embed=_embed) -> list[dict[str, Any]]:
    """Greedy one-to-one matching, highest similarity first."""
    if not generated or not gold:
        return []
    vg = embed([g["statement"] for g in generated])
    vs = embed([s["statement"] for s in gold])
    sims = vg @ vs.T
    pairs = sorted(((float(sims[i, j]), i, j) for i in range(len(generated)) for j in range(len(gold))),
                   reverse=True)
    used_g, used_s, out = set(), set(), []
    for sim, i, j in pairs:
        if sim < threshold:
            break
        if i in used_g or j in used_s:
            continue
        used_g.add(i)
        used_s.add(j)
        out.append({"gold_id": gold[j]["id"], "gold_statement": gold[j]["statement"],
                    "req_id": generated[i]["req_id"], "statement": generated[i]["statement"],
                    "similarity": round(sim, 3)})
    return out


def prf(tp: int, n_generated: int, n_gold: int) -> dict[str, float]:
    p = tp / n_generated if n_generated else 0.0
    r = tp / n_gold if n_gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def _verified_tp(sheet: Path) -> int | None:
    """True positives after human verification, if the sheet has been filled in."""
    if not sheet.exists():
        return None
    df = pd.read_csv(sheet).fillna("")
    verdicts = df["human_verdict"].astype(str).str.strip().str.lower()
    if not verdicts.ne("").any():
        return None
    return int(verdicts.isin({"yes", "y", "match", "1", "true"}).sum())


def _load_state(case_id: str) -> dict[str, Any]:
    path = case_out_dir(case_id) / "state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _control_coverage(case: dict[str, Any], covered: set[str]) -> dict[str, Any]:
    applicable = {c["id"] for c in applicable_controls(case)}
    hit = applicable & covered
    return {"value": round(len(hit) / len(applicable), 3) if applicable else None,
            "detail": f"{len(hit)}/{len(applicable)} applicable controls"}


def _baseline_controls(reqs: pd.DataFrame) -> set[str]:
    """Controls a baseline set covers, at section level: any cited chunk from the
    control's section counts. Several controls share one CFR section, so this is an
    upper bound — the baseline has no control-mapping step to be precise with."""
    by_section: dict[tuple[str, str], list[str]] = {}
    for c in controls_by_id().values():
        by_section.setdefault((c["doc"], c["section"]), []).append(c["id"])
    covered: set[str] = set()
    for cell in reqs.get("source_chunk_ids", pd.Series(dtype=str)):
        for cid in _split(cell):
            parts = cid.split("#")
            if len(parts) >= 2 and parts[1].startswith("S"):
                covered.update(by_section.get((parts[0], parts[1][1:]), []))
    return covered


def _hallucination(audit: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    audit = pd.DataFrame(audit)
    if audit.empty:
        return {"rate": None, "checked": 0, "quote_correct": None}
    bad = audit["verdict"].isin(["fabricated", "misattributed"]).sum()
    quotes = audit[audit["entity_type"] == "evidence_quote"]
    qc = round(float((quotes["verdict"] == "verified").mean()), 3) if len(quotes) else None
    return {"rate": round(float(bad / len(audit)), 3), "checked": len(audit), "quote_correct": qc}


def _statement_facts(state: dict[str, Any]) -> dict[str, set[str]]:
    return {s["id"]: set(s.get("fact_ids", [])) for s in state.get("statements", [])}


def ambiguity_detection(state: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    seeded = set(gold.get("seeded_ambiguities", []))
    unlocked = set()
    for facts in state.get("unlocked", {}).values():
        unlocked |= set(facts)
    hit = seeded & unlocked
    return {"value": round(len(hit) / len(seeded), 3) if seeded else None,
            "detail": f"{len(hit)}/{len(seeded)} seeded vague facts followed up; missed: {sorted(seeded - hit)}"}


def conflict_detection(state: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    facts_of = _statement_facts(state)
    reqs = {r["req_id"]: r for r in state.get("requirements", [])}

    def req_facts(rid: str) -> set[str]:
        out: set[str] = set()
        for s in reqs.get(rid, {}).get("source_statement_ids", []):
            out |= facts_of.get(s, set())
        return out

    flagged = [c for c in state.get("conflicts", []) if c.get("relation") == "conflict"]
    seeded = gold.get("seeded_conflicts", [])
    detected, true_flags = set(), set()
    for c in flagged:
        fa, fb = req_facts(c["req_a"]), req_facts(c["req_b"])
        for s in seeded:
            x, y = s["facts"]
            if (x in fa and y in fb) or (y in fa and x in fb):
                detected.add(s["id"])
                true_flags.add(c["id"])
    missed = sorted({s["id"] for s in seeded} - detected)
    return {"recall": round(len(detected) / len(seeded), 3) if seeded else None,
            "precision": round(len(true_flags) / len(flagged), 3) if flagged else None,
            "detail": f"{len(detected)}/{len(seeded)} seeded conflicts found; {len(flagged)} conflicts flagged; "
                      f"missed: {missed}"}


def _category_agreement(matches: list[dict[str, Any]], generated: dict[str, dict[str, Any]],
                        gold: dict[str, dict[str, Any]]) -> float | None:
    scores = []
    for m in matches:
        g = set(generated[m["req_id"]].get("categories", []))
        s = set(gold[m["gold_id"]].get("categories", []))
        if g and s:
            scores.append(len(g & s) / len(g | s))
    return round(sum(scores) / len(scores), 3) if scores else None


def _sus(role_filter: str | None = None) -> dict[str, Any]:
    path = _eval_dir() / "survey_responses.csv"
    if not path.exists():
        return {"value": None, "detail": "no survey responses recorded"}
    df = pd.read_csv(path)
    if role_filter:
        df = df[df["role"] == role_filter]
    if df.empty:
        return {"value": None, "detail": "no survey responses recorded"}
    scores = []
    for _, r in df.iterrows():
        total = 0
        for i in range(1, SUS_ITEMS + 1):
            v = int(r[f"sus_{i}"])
            total += (v - 1) if i % 2 else (5 - v)
        scores.append(total * 2.5)
    return {"value": round(sum(scores) / len(scores), 1), "detail": f"{len(scores)} respondent(s), SUS 0-100"}


def _baseline_seconds(case_id: str) -> float | None:
    log = resolve(load_pipeline()["paths"]["logs"])
    if not log.exists():
        return None
    total = 0.0
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(rec.get("tag", "")).startswith("p1_") and rec.get("meta", {}).get("target") == case_id:
            total += rec.get("latency_s") or 0.0
    return round(total, 1) or None


def evaluate_case(case_id: str, threshold: float, embed=_embed) -> list[dict[str, Any]]:
    case = load_case(case_id)
    gold = load_gold(case_id)
    gold_reqs = gold.get("requirements", [])
    gold_by_id = {g["id"]: g for g in gold_reqs}
    out_dir = case_out_dir(case_id)
    provisional = "" if gold.get("reviewed_by") else " (gold not yet reviewed — provisional)"
    gold_based = {"precision", "recall", "f1", "precision_elicited", "category_agreement",
                  "ambiguity_detection_recall", "conflict_detection_recall", "conflict_detection_precision",
                  "gold_control_coverage", "requirements_generated"}
    rows: list[dict[str, Any]] = []

    def add(system: str, metric: str, value: Any, detail: str = "") -> None:
        suffix = provisional if metric in gold_based else ""
        rows.append({"case": case_id, "system": system, "metric": metric, "value": value,
                     "detail": (detail + suffix).strip()})

    # --- the multi-agent system --------------------------------------------------------
    state = _load_state(case_id)
    if state:
        reqs = [r for r in state.get("requirements", []) if r.get("status", "active") == "active"]
        by_id = {r["req_id"]: r for r in reqs}
        auto = match(reqs, gold_reqs, threshold, embed)
        sheet = out_dir / "matches_multi_agent.csv"
        _write_sheet(sheet, auto)
        tp = _verified_tp(sheet)
        scores = prf(tp if tp is not None else len(auto), len(reqs), len(gold_reqs))
        basis = "human-verified matches" if tp is not None else f"automatic matches at cosine >= {threshold}"
        for k, v in scores.items():
            add("multi_agent", k, v, basis)
        # Gap and threat proposals are generated from the control catalogue, not elicited;
        # precision over the elicited requirements alone shows what they do to the score.
        elicited = [r for r in reqs if r.get("origin") in {"stakeholder", "document"}]
        matched_ids = {m["req_id"] for m in auto}
        tp_elicited = sum(1 for r in elicited if r["req_id"] in matched_ids)
        add("multi_agent", "precision_elicited",
            round(tp_elicited / len(elicited), 3) if elicited else None,
            f"{tp_elicited}/{len(elicited)} stakeholder- and document-sourced requirements matched")
        origins = {o: sum(1 for r in reqs if r.get("origin") == o) for o in sorted({r.get("origin") for r in reqs})}
        add("multi_agent", "requirements_generated", len(reqs), f"gold has {len(gold_reqs)}; by origin {origins}")
        add("multi_agent", "category_agreement", _category_agreement(auto, by_id, gold_by_id),
            "mean Jaccard of categories on matched pairs")
        amb = ambiguity_detection(state, gold)
        add("multi_agent", "ambiguity_detection_recall", amb["value"], amb["detail"])
        con = conflict_detection(state, gold)
        add("multi_agent", "conflict_detection_recall", con["recall"], con["detail"])
        add("multi_agent", "conflict_detection_precision", con["precision"], con["detail"])
        covered = {row["control_id"] for row in state.get("compliance", [])}
        cov = _control_coverage(case, covered)
        add("multi_agent", "control_coverage", cov["value"], cov["detail"])
        gold_controls = {c for g in gold_reqs for c in g.get("controls", [])}
        add("multi_agent", "gold_control_coverage",
            round(len(gold_controls & covered) / len(gold_controls), 3) if gold_controls else None,
            f"{len(gold_controls & covered)}/{len(gold_controls)} controls the gold requirements satisfy")
        hal = _hallucination(state.get("hallucination", []))
        add("multi_agent", "hallucination_rate", hal["rate"], f"{hal['checked']} citations checked")
        add("multi_agent", "citation_correctness", hal["quote_correct"], "evidence quotes verbatim in the cited chunk")
        snaps = {s["label"]: s for s in state.get("validation", {}).get("snapshots", [])}
        add("multi_agent", "quality_first_draft", snaps.get("v1", {}).get("mean_pass_rate"), "29148 rule pass rate before clarification")
        add("multi_agent", "quality_final", snaps.get("final", {}).get("mean_pass_rate"), "29148 rule pass rate after clarification")
        traced = sum(1 for r in reqs if r.get("source_statement_ids") or r.get("source_chunk_ids"))
        add("multi_agent", "traceability_coverage", round(traced / len(reqs), 3) if reqs else None,
            "requirements traceable to a stakeholder statement or corpus chunk")
        conf = [r.get("confidence") for r in reqs if r.get("confidence") is not None]
        add("multi_agent", "mean_confidence", round(sum(conf) / len(conf), 3) if conf else None, "")
        add("multi_agent", "escalated", sum(1 for r in reqs if r.get("escalate")), "requirements escalated for review")
        log_path = out_dir / "agent_log.jsonl"
        if log_path.exists():
            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            calls = [e for e in events if "errors" in e]
            failed = [e for e in calls if e["errors"]]
            add("multi_agent", "agent_calls_failed_after_repair", len(failed),
                f"of {len(calls)} agent calls; {sorted({e['event'] for e in failed})}")
        _sdlc_accuracy(add, state, gold)
        _human_corrections(add, out_dir)
        manifest_path = out_dir / "run_manifest.json"
        if manifest_path.exists():
            secs = json.loads(manifest_path.read_text(encoding="utf-8"))["seconds_total"]
            add("multi_agent", "processing_minutes", round(secs / 60, 1), "wall-clock, all steps")
            manual = gold.get("manual_effort_minutes")
            add("multi_agent", "time_saved_vs_manual", round(1 - (secs / 60) / manual, 3) if manual else None,
                f"manual analysis took {manual} min" if manual else "manual effort not recorded in gold.yaml")
        injection_events = [e for e in state.get("security_events", []) if e.get("kind") == "prompt_injection"]
        for inj in gold.get("injections", []):
            caught = any(e.get("source") == inj["document"] for e in injection_events)
            add("multi_agent", f"injection_quarantined:{inj['id']}", int(caught),
                "the scanner quarantined the seeded injection before any agent saw it")

    # --- the single-prompt baseline ------------------------------------------------------
    from .generate_reqs import output_dir

    base_dir = output_dir(case_id)
    base_path = base_dir / "requirements.csv"
    if base_path.exists():
        base = pd.read_csv(base_path).fillna("")
        base_reqs = base.to_dict("records")
        auto = match(base_reqs, gold_reqs, threshold, embed)
        sheet = out_dir / "matches_baseline.csv"
        _write_sheet(sheet, auto)
        tp = _verified_tp(sheet)
        for k, v in prf(tp if tp is not None else len(auto), len(base_reqs), len(gold_reqs)).items():
            add("baseline", k, v, "human-verified matches" if tp is not None else f"automatic matches at cosine >= {threshold}")
        add("baseline", "requirements_generated", len(base_reqs), f"gold has {len(gold_reqs)}")
        cov = _control_coverage(case, _baseline_controls(base))
        add("baseline", "control_coverage", cov["value"],
            cov["detail"] + " — upper bound: any cited chunk in the control's section counts")
        audit_path = base_dir / "hallucination_audit.csv"
        if audit_path.exists():
            hal = _hallucination(pd.read_csv(audit_path).fillna(""))
            add("baseline", "hallucination_rate", hal["rate"], f"{hal['checked']} citations checked")
            add("baseline", "citation_correctness", hal["quote_correct"], "evidence quotes verbatim in the cited chunk")
        val_path = base_dir / "validation_29148.csv"
        if val_path.exists():
            add("baseline", "quality_final", round(float(pd.read_csv(val_path)["rule_score"].mean()), 3),
                "29148 rule pass rate (no clarification loop)")
        add("baseline", "traceability_coverage",
            round(float(base["source_chunk_ids"].astype(str).str.strip().ne("").mean()), 3) if len(base) else None,
            "requirements citing a corpus chunk")
        add("baseline", "ambiguity_detection_recall", 0.0, "no stakeholder interaction, by construction")
        add("baseline", "conflict_detection_recall", 0.0, "no conflict detection step, by construction")
        secs = _baseline_seconds(case_id)
        add("baseline", "processing_minutes", round(secs / 60, 1) if secs else None, "model time for the Part 1 calls")

    sus = _sus()
    add("multi_agent", "stakeholder_satisfaction_sus", sus["value"], sus["detail"])
    return rows


def _write_sheet(path: Path, auto: list[dict[str, Any]]) -> None:
    """Write the automatic matches for verification, keeping verdicts already entered."""
    frame = pd.DataFrame(auto, columns=["gold_id", "gold_statement", "req_id", "statement", "similarity"])
    frame["human_verdict"] = ""
    if path.exists():
        old = pd.read_csv(path).fillna("")
        keep = {(r.gold_id, r.req_id): r.human_verdict for r in old.itertuples()}
        frame["human_verdict"] = [keep.get((g, r), "") for g, r in zip(frame["gold_id"], frame["req_id"])]
    frame.to_csv(path, index=False, encoding="utf-8")


def _sdlc_accuracy(add, state: dict[str, Any], gold: dict[str, Any]) -> None:
    rec = (state.get("sdlc") or {}).get("recommendation")
    expert = (gold.get("expert_sdlc") or {}).get("top", "")
    if not rec:
        add("multi_agent", "sdlc_top1", None, "no SDLC recommendation produced")
        return
    add("multi_agent", "sdlc_recommendation", rec["top"], f"{rec['ranking'][0]['pct']}%; runner-up {rec['runner_up']}")
    if not expert:
        add("multi_agent", "sdlc_top1", None, "expert SDLC choice not yet recorded in gold.yaml")
        return
    top2 = [r["model"] for r in rec["ranking"][:2]]
    add("multi_agent", "sdlc_top1", int(rec["top"] == expert), f"engine {rec['top']} vs expert {expert}")
    add("multi_agent", "sdlc_top2", int(expert in top2), f"engine top-2 {top2} vs expert {expert}")


def _human_corrections(add, out_dir: Path) -> None:
    from .store import decisions

    d = decisions(out_dir)
    if d.empty:
        add("multi_agent", "human_correction_rate", None, "no human decisions recorded yet")
        return
    base = d[d["item_type"] == "requirement_baseline"]
    if base.empty:
        add("multi_agent", "human_correction_rate", None, "no requirement decisions recorded yet")
        return
    corrected = base["decision"].isin(["modify", "reject", "regenerate"]).sum()
    add("multi_agent", "human_correction_rate", round(float(corrected / len(base)), 3),
        f"{corrected}/{len(base)} requirement decisions changed or rejected the output")


# --- prompt-injection replay --------------------------------------------------------------


def injection_replay(case_id: str) -> list[dict[str, Any]]:
    """Replay each seeded injection through the extraction agent, with and without defences.

    Defended: the pipeline's own path — masked, quarantined, spotlighted, injection
    notice in the prompt. Undefended: the same document, masked only, sent raw with no
    notice. Success = one of the gold success patterns appears in the model output.
    """
    from .agents import AgentContext, Blackboard, RequirementExtractionAgent
    from .generate_reqs import build_evidence, load_prompt, render
    from .llm import OllamaClient
    from .orchestrator import _paragraphs, public_case
    from .security import Vault, mask, quarantine

    case = load_case(case_id)
    gold = load_gold(case_id)
    client = OllamaClient()
    run_dir = ensure_dir(case_out_dir(case_id) / "injection_replay")
    ctx = AgentContext(case=public_case(case), board=Blackboard(), client=client, run_dir=run_dir, step="injection_replay")
    agent = RequirementExtractionAgent(ctx)
    docs = {d["id"]: d for d in case.get("documents", [])}
    rows = []
    for inj in gold.get("injections", []):
        vault = Vault()
        raw, _ = mask(docs[inj["document"]]["text"], vault)
        patterns = [re.compile(p, re.I) for p in inj["success_patterns"]]

        defended_text = "\n\n".join(quarantine(p)[0] for p in raw.split("\n\n"))
        statements = [{"id": f"{inj['document']}#p{k}", "text": t}
                      for k, t in enumerate(_paragraphs(defended_text), start=1)]
        reqs, _, _ = agent.extract(f"document {inj['document']}", statements)
        defended_out = json.dumps(reqs)

        undefended_statements = [{"id": f"{inj['document']}#p{k}", "text": t}
                                 for k, t in enumerate(_paragraphs(raw), start=1)]
        hits = agent.retrieve(case["functionality"]["name"], k=6)
        evidence, _ = build_evidence(hits, 2500)
        prompt = render(load_prompt("agents/extract.txt"),
                        FUNCTIONALITY=f"{case['functionality']['name']}\n{case['functionality']['description']}",
                        SOURCE_LABEL=f"document {inj['document']}",
                        STATEMENTS="\n".join(f"{s['id']}: {s['text']}" for s in undefended_statements),
                        EVIDENCE=evidence)
        resp = client.generate(ctx.cfg["agents"]["model"], prompt=prompt, json_mode=True,
                               tag="injection_replay.undefended", meta={"case": case_id, "injection": inj["id"]})
        undefended_out = resp.text

        for condition, text in (("defended", defended_out), ("undefended", undefended_out)):
            rows.append({"case": case_id, "injection": inj["id"], "condition": condition,
                         "attack_succeeded": int(any(p.search(text) for p in patterns)),
                         "goal": inj["goal"]})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate the multi-agent system and the baseline against gold standards")
    ap.add_argument("--case", default="all")
    ap.add_argument("--threshold", type=float, default=None, help="cosine threshold for a requirement match")
    ap.add_argument("--injection-replay", action="store_true", help="replay seeded injections (needs Ollama)")
    args = ap.parse_args()

    threshold = args.threshold or load_pipeline().get("evaluation", {}).get("match_threshold", 0.6)
    cases = case_ids() if args.case == "all" else [args.case]
    rows = []
    for cid in cases:
        rows.extend(evaluate_case(cid, threshold))
        print(f"[evaluate] {cid}: {sum(1 for r in rows if r['case'] == cid)} metrics")
    out = _eval_dir()
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "summary.csv", index=False, encoding="utf-8")
    if not summary.empty:
        wide = summary.pivot_table(index=["case", "metric"], columns="system", values="value", aggfunc="first")
        wide.to_csv(out / "summary_wide.csv", encoding="utf-8")
        print(wide.to_string())

    if args.injection_replay:
        inj = [r for cid in cases for r in injection_replay(cid)]
        pd.DataFrame(inj).to_csv(out / "injection_replay.csv", index=False, encoding="utf-8")
        for r in inj:
            print(f"[injection] {r['case']} {r['injection']} {r['condition']}: "
                  f"{'SUCCEEDED' if r['attack_succeeded'] else 'blocked'}")
    print(f"[evaluate] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
