"""Clarification agent (brief point 10: failing requirements return for clarification).

Each requirement with an open, clarifiable finding — ambiguity, an incomplete or
untestable acceptance criterion, a missing source, an undefined term — is routed to
the stakeholder whose statement it came from (document-sourced requirements go to
the product owner), and one targeted question is written for it. The coordinator
collects the answers and has the extraction agent revise the requirement; findings
the revision does not clear stay open and are escalated after the last round.

Conflicts are not clarified here: each side holds its position by design, and
settling a conflict between stakeholders is a human decision (brief point 16).
"""

from __future__ import annotations

from typing import Any

from ..security import spotlight
from .base import Agent, active, expect_list, items

CLARIFIABLE = {"ambiguity", "incomplete", "untestable", "missing_source", "undefined_term"}

TEMPLATES = {
    "ambiguity": "The requirement says \"{snippet}\". What exact number, limit or rule do you need here?",
    "incomplete": "How would you check that \"{snippet}\" is working — what would you look for?",
    "untestable": "What result would show that \"{snippet}\" has been met?",
    "missing_source": "Do you need \"{snippet}\", and if so, why?",
    "undefined_term": "In \"{snippet}\", what does the term used mean?",
}


class ClarificationAgent(Agent):
    name = "clarification"

    def open_issues(self) -> dict[str, list[dict[str, Any]]]:
        live = {r["req_id"] for r in active(self.read("requirements", []))}
        out: dict[str, list[dict[str, Any]]] = {}
        for f in self.read("findings", []):
            if not f.get("resolved") and f["kind"] in CLARIFIABLE and f["req_id"] in live:
                out.setdefault(f["req_id"], []).append(f)
        return out

    def plan(self, stakeholders: list[dict[str, Any]], round_no: int) -> dict[str, list[dict[str, Any]]]:
        """-> {stakeholder id: [question for one requirement, ...]}"""
        reqs = {r["req_id"]: r for r in active(self.read("requirements", []))}
        statements = {s["id"]: s for s in self.read("statements", [])}
        issues = self.open_issues()
        if not issues:
            return {}
        default = next((s["id"] for s in stakeholders if s["role"] == "product_owner"), stakeholders[0]["id"])

        route: dict[str, list[str]] = {}
        for rid in issues:
            owner = next((statements[s]["stakeholder"] for s in reqs[rid].get("source_statement_ids", [])
                          if s in statements and statements[s].get("stakeholder")), None)
            route.setdefault(owner or default, []).append(rid)

        plan: dict[str, list[dict[str, Any]]] = {}
        for sid, rids in route.items():
            role = next((s["role"] for s in stakeholders if s["id"] == sid), "stakeholder")
            lines = []
            for rid in rids:
                said = " / ".join(statements[s]["text"] for s in reqs[rid].get("source_statement_ids", [])
                                  if s in statements)[:300]
                problems = "; ".join(f"{f['kind']}: {f['detail']}" for f in issues[rid])
                lines.append(f"{rid} | {problems} | {reqs[rid]['statement']} | {said or '(document)'}")

            def check(p: Any, rids=set(rids)) -> list[str]:
                errs = expect_list(p, "questions", 1)
                missing = rids - {q.get("req_id") for q in items(p, "questions")}
                if missing:
                    errs.append(f"no question for {sorted(missing)}")
                return errs

            payload, _ = self.ask(
                "clarify_questions",
                {"STAKEHOLDER": role.replace("_", " "),
                 "ITEMS": spotlight("\n".join(lines), f"clarification:{sid}")},
                check, tag=f"questions.r{round_no}.{sid}",
            )
            asked = {q["req_id"]: str(q.get("question", "")).strip()
                     for q in items(payload, "questions") if q.get("req_id") in rids}
            plan[sid] = [
                {"id": f"CQ{round_no}-{sid}-{k}", "req_id": rid,
                 "question": asked.get(rid) or self._template(reqs[rid], issues[rid]),
                 "issues": [f["kind"] for f in issues[rid]]}
                for k, rid in enumerate(rids, start=1)
            ]
        return plan

    @staticmethod
    def _template(req: dict[str, Any], issues: list[dict[str, Any]]) -> str:
        snippet = req["statement"][:110]
        return TEMPLATES.get(issues[0]["kind"], TEMPLATES["ambiguity"]).format(snippet=snippet)

    def record(self, entries: list[dict[str, Any]]) -> None:
        log = self.read("clarifications", [])
        log.extend(entries)
        self.write("clarifications", log)
