"""Validation agent (brief points 6 and 10).

Runs exactly the scorers the baseline is judged with (src/validate.py), so the two
are comparable:

  * The ISO/IEC/IEEE 29148 rule scorer. Each failed attribute becomes a typed
    finding — ambiguity, incomplete, untestable, non_singular, missing_source,
    infeasible, duplicate, nonconforming — which is what the clarification loop
    works from. The undefined-terminology check (acronyms missing from the glossary)
    adds `undefined_term` findings.
  * A quality snapshot before clarification ("v1") and after it ("final"). The
    first-draft quality is reported, not only the repaired quality — the audit
    measures the model, it does not launder it.
  * On the final set: the LLM critic, the hallucination audit, and per-requirement
    confidence with the escalation decision.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .. import validate
from .base import Agent, active

ATTR_TO_KIND = {
    "unambiguous": "ambiguity", "complete": "incomplete", "verifiable": "untestable",
    "singular": "non_singular", "traceable": "missing_source", "feasible": "infeasible",
    "necessary": "duplicate", "conforming": "nonconforming",
}
_ACRONYM = re.compile(r"(?<![\w\[])([0-9]?[A-Z][A-Z0-9]{1,7})(?![\w\]])")
_LIST_FIELDS = ("source_statement_ids", "source_chunk_ids", "invalid_chunk_ids", "categories",
                "regulations", "control_ids", "assumptions", "dependencies")


def to_frame(reqs: list[dict[str, Any]]) -> pd.DataFrame:
    """Requirements as the validate.py scorers expect them: lists joined with ';'."""
    rows = []
    for r in reqs:
        row = dict(r)
        for f in _LIST_FIELDS:
            if isinstance(row.get(f), list):
                row[f] = ";".join(str(x) for x in row[f])
        rows.append(row)
    return pd.DataFrame(rows)


class ValidationAgent(Agent):
    name = "validation"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        glossary = {g.upper() for g in ctx.cfg["validation"].get("glossary", [])}
        # Id prefixes and masking-token names are not terminology.
        ids = {"FR", "NFR", "REQ", "CQ", "TH", "RK", "CF", "UC", "APR",
               str(ctx.case.get("id_prefix", "")).upper()}
        tokens = {"PERSON", "SSN", "DOB", "EMAIL", "PHONE", "ADDRESS", "CARD"}
        self.known_terms = glossary | ids | tokens

    def undefined_terms(self, text: str) -> list[str]:
        return sorted({t for t in _ACRONYM.findall(text) if t.upper() not in self.known_terms})

    def check_quality(self, label: str, round_no: int = 0) -> dict[str, Any]:
        """Rule-score the live set, sync findings, and store a quality snapshot."""
        reqs = self.read("requirements", [])
        live = active(reqs)
        if not live:
            return {"label": label, "n": 0}
        scores = validate.score_rules(to_frame(live))
        findings = self.read("findings", [])
        failing: dict[str, dict[str, str]] = {}
        for _, s in scores[scores["rule_score"] == 0].iterrows():
            failing.setdefault(s["req_id"], {})[ATTR_TO_KIND[s["attribute"]]] = s["rule_note"]
        for r in live:
            terms = self.undefined_terms(f"{r['statement']} {r.get('acceptance_criteria', '')}")
            if terms:
                failing.setdefault(r["req_id"], {})["undefined_term"] = "undefined term(s): " + ", ".join(terms)

        # Resolve findings that no longer fail; add the new ones.
        rule_kinds = set(ATTR_TO_KIND.values()) | {"undefined_term"}
        live_ids = {r["req_id"] for r in live}
        for f in findings:
            if (f["source"] == "rule" and f["kind"] in rule_kinds and not f.get("resolved")
                    and f["req_id"] in live_ids and f["kind"] not in failing.get(f["req_id"], {})):
                f["resolved"] = True
                f["resolved_round"] = round_no
        open_keys = {(f["req_id"], f["kind"]) for f in findings if not f.get("resolved")}
        for rid, kinds in failing.items():
            for kind, detail in kinds.items():
                if (rid, kind) not in open_keys:
                    findings.append({"req_id": rid, "kind": kind, "source": "rule", "detail": detail,
                                     "round": round_no, "resolved": False})
        self.write("findings", findings)

        pass_rates = scores.groupby("attribute")["rule_score"].mean().round(3).to_dict()
        snapshot = {"label": label, "n": len(live), "pass_rate": pass_rates,
                    "mean_pass_rate": round(float(scores["rule_score"].mean()), 3),
                    "requirements_failing": len(failing)}
        state = self.read("validation", {}) or {}
        state.setdefault("snapshots", []).append(snapshot)
        self.write("validation", state)
        return snapshot

    def final(self, critic: bool) -> dict[str, Any]:
        reqs = self.read("requirements", [])
        live = active(reqs)
        frame = to_frame(live)
        rules = validate.score_rules(frame)
        critic_scores = None
        if critic:
            try:
                critic_scores = validate.score_critic(frame, self.model_key, client=self.ctx.client)
            except Exception as exc:  # the critic is advisory; its failure must not stop the run
                self.ctx.log(self.name, "critic_failed", error=str(exc))
        merged = validate.merge_scores(rules, critic_scores)
        audit = validate.audit_hallucinations(frame)

        open_conflicts = {f["req_id"] for f in self.read("findings", [])
                          if f["kind"] == "conflict" and not f.get("resolved")}
        conf = validate.confidence_table(frame, merged, audit, conflicted=open_conflicts)
        by_id = conf.set_index("req_id").to_dict("index")
        for r in live:
            c = by_id.get(r["req_id"], {})
            r["confidence"] = c.get("confidence")
            r["escalate"] = bool(c.get("escalate"))
            r["confidence_reasons"] = c.get("reasons", "")
        self.write("requirements", reqs)

        state = self.read("validation", {}) or {}
        state["scores"] = merged.to_dict("records")
        self.write("validation", state)
        self.write("hallucination", audit.to_dict("records"))
        self.write("confidence", conf.to_dict("records"))
        snapshot = self.check_quality("final", round_no=99)
        return {
            "requirements": len(live),
            "mean_confidence": round(float(conf["confidence"].mean()), 3) if len(conf) else None,
            "escalated": int(conf["escalate"].sum()) if len(conf) else 0,
            "hallucination_suspect": int(audit["verdict"].isin(["fabricated", "misattributed"]).sum())
            if len(audit) else 0,
            "final_mean_pass_rate": snapshot.get("mean_pass_rate"),
        }
