"""SDLC selection agent (brief points 13-15).

  1. Perception — both models score the brief's 13 decision factors from the
     requirement set and the project context, each score justified with req_ids.
  2. Decision — the median scores go to the deterministic engine (rules + MCDA),
     which ranks every model with a suitability percentage.
  3. Explanation — the model explains the engine's ranking; it cannot change it.
  4. Workflow — the top model's template is instantiated with security, compliance
     and clinical-safety overlays, and the model adds project-specific activities.

Factors on which the two models differ by two points or more are reported as
contested. The recommendation is always pending approval by the project manager,
architect, security officer and compliance officer.
"""

from __future__ import annotations

from typing import Any

from ..sdlc_engine import (aggregate, build_workflow, factor_names, load_sdlc, recommend,
                           workflow_markdown, workflow_mermaid)
from ..security import spotlight
from .base import Agent, active, as_list, items

APPROVERS = ["project_manager", "architect", "security_officer", "compliance_officer"]


class SDLCSelectionAgent(Agent):
    name = "sdlc_selection"

    def _functionality(self) -> str:
        fn = self.ctx.case["functionality"]
        return f"{fn['name']}\n{fn['description'].strip()}"

    def score_factors(self, model_key: str, live: list[dict[str, Any]]) -> dict[str, Any]:
        ids = {r["req_id"] for r in live}
        names = factor_names()
        table = "\n".join(
            f"{r['req_id']} | {r.get('type', '')} | {','.join(r.get('categories', []))} | "
            f"{r.get('risk_level', '')} | {r.get('volatility', '')} | {r.get('priority', '')} | {r['statement']}"
            for r in live
        )
        factors = "\n".join(f"{n}: 1 = {s['low']}; 5 = {s['high']}" for n, s in load_sdlc()["factors"].items())

        def check(p: Any) -> list[str]:
            errs = []
            got = {}
            for x in items(p, "factors"):
                try:
                    score = int(x.get("score"))
                except (TypeError, ValueError):
                    errs.append(f"{x.get('factor')}: score must be an integer 1-5")
                    continue
                if x.get("factor") in names and 1 <= score <= 5:
                    got[x["factor"]] = score
                unknown = [c for c in as_list(x.get("cited_req_ids")) if c not in ids]
                if unknown:
                    errs.append(f"{x.get('factor')}: cites unknown req_ids {unknown}")
            errs += [f"missing factor {n}" for n in names if n not in got]
            return errs

        payload, errors = self.ask(
            "sdlc_factors",
            {"FUNCTIONALITY": self._functionality(),
             "CONTEXT": spotlight(self.ctx.case.get("project_context", "").strip(), "project_context"),
             "REQUIREMENTS": table, "FACTORS": factors, "N_FACTORS": str(len(names))},
            check, tag=f"factors.{model_key}", model_key=model_key,
        )
        scores, notes = {}, {}
        for x in items(payload, "factors"):
            try:
                score = int(x.get("score"))
            except (TypeError, ValueError):
                continue
            if x.get("factor") in names and 1 <= score <= 5:
                scores[x["factor"]] = score
                notes[x["factor"]] = {"justification": str(x.get("justification", "")),
                                      "cited_req_ids": [c for c in as_list(x.get("cited_req_ids")) if c in ids]}
        return {"model_key": model_key, "scores": scores, "justifications": notes, "errors": errors}

    def run(self) -> dict[str, Any]:
        reqs = self.read("requirements", [])
        live = active(reqs)
        ids = {r["req_id"] for r in live}
        models = [self.ctx.cfg["agents"]["model"], self.ctx.cfg["agents"]["persona_model"]]
        scored = [self.score_factors(mk, live) for mk in dict.fromkeys(models)]
        usable = [s["scores"] for s in scored if len(s["scores"]) >= len(factor_names()) - 2]
        agg = aggregate(usable or [s["scores"] for s in scored])
        if not agg:
            record = {"status": "failed", "reason": "no model produced usable factor scores",
                      "factor_scores": scored, "approval_roles": APPROVERS}
            self.write("sdlc", record)
            return record

        contested = []
        if len(scored) == 2:
            a, b = scored[0]["scores"], scored[1]["scores"]
            contested = [f for f in factor_names() if f in a and f in b and abs(a[f] - b[f]) >= 2]
        rec = recommend(agg)
        if contested:
            rec["escalate"] = True
            rec["escalation_reasons"].append("the two models disagree by 2+ points on: " + ", ".join(contested))

        explanation = self._explain(rec, scored[0], ids)
        source_docs = {c.split("#")[0] for r in live for c in r.get("source_chunk_ids", [])}
        source_docs |= {row["evidence_chunk_id"].split("#")[0] for row in self.read("compliance", [])
                        if row.get("evidence_chunk_id")}
        safety = any(r.get("risk_class") == "Safety-critical" for r in live)
        workflow = build_workflow(rec["top"], source_docs, safety, float(agg.get("security_risk", 3)))
        self._tailor(rec["top"], workflow, live)

        record = {
            "status": "pending_approval", "factor_scores": scored, "aggregate": agg,
            "contested_factors": contested, "recommendation": rec, "explanation": explanation,
            "workflow": workflow, "workflow_markdown": workflow_markdown(rec["top"], workflow),
            "workflow_mermaid": workflow_mermaid(workflow), "source_docs": sorted(source_docs),
            "safety_critical": safety, "approval_roles": APPROVERS,
        }
        self.write("sdlc", record)
        return {"top": rec["top"], "top_pct": rec["ranking"][0]["pct"], "runner_up": rec["runner_up"],
                "escalate": rec["escalate"]}

    def _explain(self, rec: dict[str, Any], primary: dict[str, Any], ids: set[str]) -> dict[str, Any]:
        def line(f: str, s: float) -> str:
            note = primary["justifications"].get(f, {})
            cites = ", ".join(note.get("cited_req_ids", []))
            return f"{f}: {s:g} — {note.get('justification', '')}" + (f" (cites {cites})" if cites else "")

        factor_lines = "\n".join(line(f, s) for f, s in rec["scores"].items())
        ranking = "\n".join(f"{r['model']}: {r['pct']}% (rules: {', '.join(r['rule_support']) or 'none'})"
                            for r in rec["ranking"])

        def check(p: Any) -> list[str]:
            if not isinstance(p, dict) or not str(p.get("explanation", "")).strip():
                return ["'explanation' must be a non-empty string"]
            cited = [c for c in as_list(p.get("cited_req_ids")) if c in ids]
            return [] if len(cited) >= 2 else ["cite at least two req_ids from the requirement set"]

        payload, errors = self.ask(
            "sdlc_explain",
            {"FUNCTIONALITY": self._functionality(), "FACTORS": factor_lines, "RANKING": ranking,
             "RULES": "; ".join(f"{r['id']} ({r['brief_condition']}) -> {r['model']}" for r in rec["fired_rules"])
             or "none", "CAUTIONS": " ".join(rec["cautions"]) or "none",
             "TOP": rec["top"], "RUNNER_UP": rec["runner_up"]},
            check, tag="explain",
        )
        if not isinstance(payload, dict):
            return {"explanation": "", "errors": errors}
        return {"explanation": str(payload.get("explanation", "")),
                "decisive_factors": as_list(payload.get("decisive_factors")),
                "strongest_counterargument": str(payload.get("strongest_counterargument", "")),
                "cited_req_ids": [c for c in as_list(payload.get("cited_req_ids")) if c in ids],
                "errors": errors}

    def _tailor(self, model: str, workflow: list[dict[str, Any]], live: list[dict[str, Any]]) -> None:
        names = {p["name"] for p in workflow}
        ids = {r["req_id"] for r in live}
        key = sorted(live, key=lambda r: (r.get("priority") != "Must", r.get("risk_class") != "Safety-critical"))[:20]

        def check(p: Any) -> list[str]:
            errs = [f"unknown phase {x.get('phase')!r}" for x in items(p, "phases") if x.get("phase") not in names]
            return errs or ([] if items(p, "phases") else ["'phases' must list at least one phase"])

        payload, _ = self.ask(
            "workflow_tailor",
            {"MODEL": model, "FUNCTIONALITY": self._functionality(),
             "PHASES": "\n".join(f"{p['name']} | {'; '.join(p.get('activities', []))}" for p in workflow),
             "REQUIREMENTS": "\n".join(f"{r['req_id']}: {r['statement']}" for r in key)},
            check, tag="tailor",
        )
        tailored = {x.get("phase"): x for x in items(payload, "phases") if x.get("phase") in names}
        for p in workflow:
            x = tailored.get(p["name"])
            p["tailored"] = [str(a) for a in as_list(x.get("activities"))] if x else []
            p["tailored_req_ids"] = [c for c in as_list(x.get("req_ids")) if c in ids] if x else []
