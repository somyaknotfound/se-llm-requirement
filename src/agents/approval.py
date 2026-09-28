"""Human-approval agent (brief point 16).

Builds the approval queue: every decision the brief says must stay with a person,
routed to the role with authority for it (config/stakeholders.yaml ->
approval_authority). It never decides anything. Each item is created `pending`;
accept, reject, modify and regenerate are recorded by src/approve.py or the web UI
under the reviewer's authenticated identity.

    requirement_baseline        every requirement                         product owner
    regulatory_interpretation   every proposed control mapping and gap    compliance officer
    security_requirement        security/privacy requirements, threat proposals   security officer
    clinical_safety             safety-critical requirements               clinical safety officer
    conflict                    every open conflict between requirements   product owner
    architecture_critical       integration, performance, availability     architect
    sdlc_selection              the recommendation, per required role      PM, architect, security, compliance
    injection_quarantine        every quarantined prompt injection         security officer
    production_readiness        the gate before release, per required role PM, CSO, security, compliance

Escalated items — low confidence, unsupported, fabricated citations, contested SDLC
factors — are marked high priority and carry the reasons.
"""

from __future__ import annotations

from typing import Any

from ..knowledge import load_stakeholder_templates
from .base import Agent, active


class HumanApprovalAgent(Agent):
    name = "human_approval"

    def run(self) -> dict[str, int]:
        authority = load_stakeholder_templates()["approval_authority"]
        reqs = active(self.read("requirements", []))
        queue: list[dict[str, Any]] = []

        def add(item_type: str, item_id: str, reason: str, high: bool = False, role: str | None = None) -> None:
            roles = role or authority[item_type]
            for r in roles if isinstance(roles, list) else [roles]:
                queue.append({"id": f"APR-{len(queue) + 1:03d}", "item_type": item_type, "item_id": item_id,
                              "required_role": r, "reason": reason, "priority": "high" if high else "normal",
                              "status": "pending", "decision": "", "decided_by": "", "decided_at": "",
                              "note": "", "modified_text": ""})

        for r in reqs:
            esc = bool(r.get("escalate"))
            why = r.get("confidence_reasons") or "baseline approval"
            add("requirement_baseline", r["req_id"],
                f"confidence {r.get('confidence')}; {why}" if esc else "baseline approval", high=esc)
            cats = set(r.get("categories", []))
            if cats & {"security", "privacy"} or r.get("origin") == "security_threat":
                add("security_requirement", r["req_id"],
                    "security or privacy requirement" + (" proposed from a threat" if r.get("origin") == "security_threat" else ""),
                    high=r.get("origin") == "security_threat")
            if r.get("risk_class") == "Safety-critical":
                add("clinical_safety", r["req_id"], f"safety-critical; risk {r.get('risk_level', '')}", high=True)
            if cats & {"integration", "performance", "availability_reliability"}:
                add("architecture_critical", r["req_id"], "affects integration, performance or availability")

        by_req: dict[str, list[str]] = {}
        for row in self.read("compliance", []):
            by_req.setdefault(row["req_id"], []).append(row["citation"])
        for rid, cites in by_req.items():
            add("regulatory_interpretation", rid, "proposed mapping to " + "; ".join(sorted(set(cites))),
                high=any(r["req_id"] == rid and r.get("origin") == "compliance_gap" for r in reqs))

        for c in self.read("conflicts", []):
            if c.get("status") == "open":
                add("conflict", c["id"], f"{c['req_a']} vs {c['req_b']}: {c['explanation']}", high=True)

        for e in self.read("security_events", []):
            if e.get("kind") == "prompt_injection":
                add("injection_quarantine", e.get("source", ""), f"quarantined: {e.get('detail', '')}", high=True)

        sdlc = self.read("sdlc", {}) or {}
        rec = sdlc.get("recommendation")
        if rec:
            reason = f"recommended {rec['top']} ({rec['ranking'][0]['pct']}%), runner-up {rec['runner_up']}"
            if rec.get("escalate"):
                reason += "; escalated: " + "; ".join(rec["escalation_reasons"])
            add("sdlc_selection", rec["top"], reason, high=bool(rec.get("escalate")))
        add("production_readiness", "release", "gate before production; all approvals above must be closed")

        self.write("approvals", queue)
        return {"items": len(queue), "high_priority": sum(1 for q in queue if q["priority"] == "high")}
