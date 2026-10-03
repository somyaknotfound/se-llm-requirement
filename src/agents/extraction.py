"""Requirement-extraction agent (brief points 6 and 8).

Turns one source at a time — a stakeholder's interview, or one document — into
structured requirements linked to the statements they came from, grounded in
evidence retrieved from the authorised knowledge base (retrieval-grounded
generation). It also revises a requirement after clarification or when a reviewer
asks for regeneration.

Citation integrity is recorded, not enforced by dropping: a chunk id the model was
not shown is kept in `invalid_chunk_ids` for the hallucination audit.
"""

from __future__ import annotations

import re
from typing import Any

from ..generate_reqs import build_evidence
from ..security import spotlight
from .base import Agent, as_list, expect_list, items

ENUMS: dict[str, tuple[set[str], str]] = {
    "type": ({"FR", "NFR"}, "FR"),
    "actor": ({"prescriber", "pharmacist", "patient", "system", "auditor", "administrator"}, "system"),
    "priority": ({"Must", "Should", "Could", "Won't"}, "Should"),
    "verification_method": ({"Test", "Demonstration", "Inspection", "Analysis"}, "Test"),
    "risk_class": ({"Safety-critical", "Business-critical", "Standard"}, "Standard"),
    "volatility": ({"High", "Medium", "Low"}, "Medium"),
}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:40]


class RequirementExtractionAgent(Agent):
    name = "extraction"

    def _functionality(self) -> str:
        fn = self.ctx.case["functionality"]
        return f"{fn['name']}\n{fn['description'].strip()}"

    def extract(
        self, label: str, statements: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        """-> (requirements, unresolved errors, out-of-scope notes) for one source."""
        ids = [s["id"] for s in statements]
        block = spotlight("\n".join(f"{s['id']}: {s['text']}" for s in statements), label)
        query = f"{self.ctx.case['functionality']['name']}. " + " ".join(s["text"] for s in statements)[:1500]
        hits = self.retrieve(query, k=6)
        evidence, shown = build_evidence(hits, self.ctx.cfg["agents"].get("evidence_tokens", 2500))
        shown_set = set(shown)

        def check(p: Any) -> list[str]:
            errs = expect_list(p, "requirements", 0)
            for i, r in enumerate(items(p, "requirements"), 1):
                if "shall" not in str(r.get("statement", "")).lower():
                    errs.append(f"requirement {i}: the statement has no 'shall'")
                src = as_list(r.get("source_statement_ids"))
                if not src:
                    errs.append(f"requirement {i}: source_statement_ids is empty")
                unknown = [x for x in src if x not in ids]
                if unknown:
                    errs.append(f"requirement {i}: statement ids {unknown} are not in SOURCE STATEMENTS")
                for field, (allowed, _) in ENUMS.items():
                    if r.get(field) not in allowed:
                        errs.append(f"requirement {i}: {field}={r.get(field)!r} is not one of {sorted(allowed)}")
            return errs

        payload, errors = self.ask(
            "extract",
            {"FUNCTIONALITY": self._functionality(), "SOURCE_LABEL": label,
             "CONTEXT": spotlight(self.ctx.case.get("project_context", "").strip(), "project_context"),
             "STATEMENTS": block, "EVIDENCE": evidence or "(no evidence retrieved)"},
            check, tag=f"extract.{_slug(label)}",
        )
        reqs = []
        for r in items(payload, "requirements"):
            rec = self._normalise(r, set(ids), shown_set)
            if rec is not None:
                reqs.append(rec)
        out_of_scope = [str(x) for x in payload.get("out_of_scope", [])] if isinstance(payload, dict) else []
        return reqs, errors, out_of_scope

    def _normalise(self, r: dict[str, Any], ids: set[str], shown: set[str]) -> dict[str, Any] | None:
        statement = " ".join(str(r.get("statement", "")).split())
        sources = [s for s in as_list(r.get("source_statement_ids")) if s in ids]
        if "shall" not in statement.lower() or not sources:
            return None
        cites = as_list(r.get("source_chunk_ids"))
        rec: dict[str, Any] = {
            "statement": statement,
            "acceptance_criteria": " ".join(str(r.get("acceptance_criteria", "")).split()),
            "business_justification": " ".join(str(r.get("business_justification", "")).split()),
            "source_statement_ids": sources,
            "source_chunk_ids": [c for c in cites if c in shown],
            "invalid_chunk_ids": [c for c in cites if c not in shown],
            "evidence_quote": str(r.get("evidence_quote", "") or "").strip(),
            "derived": bool(r.get("derived")) if isinstance(r.get("derived"), bool) else False,
            "assumptions": as_list(r.get("assumptions")),
            "dependencies": as_list(r.get("dependencies")),
            "schema_defaults": [],
        }
        for field, (allowed, default) in ENUMS.items():
            value = r.get(field)
            if value not in allowed:
                rec["schema_defaults"].append(field)
                value = default
            rec[field] = value
        return rec

    def revise(self, req: dict[str, Any], issues: list[str], answers: list[dict[str, Any]],
               tag: str = "revise") -> dict[str, Any] | None:
        """Rewrite one requirement from clarification answers or a reviewer's note."""
        answer_ids = {a["id"] for a in answers}
        current = (f"{req['req_id']}: {req['statement']}\n"
                   f"acceptance criteria: {req.get('acceptance_criteria', '')}\n"
                   f"verification method: {req.get('verification_method', '')}")
        block = spotlight("\n".join(f"{a['id']}: {a['text']}" for a in answers), f"clarification:{req['req_id']}")

        def check(p: Any) -> list[str]:
            if not isinstance(p, dict):
                return ["top-level JSON must be an object"]
            errs = []
            if "shall" not in str(p.get("statement", "")).lower():
                errs.append("the revised statement has no 'shall'")
            if str(p.get("verification_method", "Test")) not in ENUMS["verification_method"][0]:
                errs.append("verification_method is not one of Test, Demonstration, Inspection, Analysis")
            return errs

        payload, errors = self.ask(
            "revise",
            {"REQUIREMENT": current, "ISSUES": "\n".join(f"- {i}" for i in issues),
             "ANSWERS": block or "(none)"},
            check, tag=f"{tag}.{req['req_id']}",
        )
        if errors or not isinstance(payload, dict):
            return None
        new_sources = [s for s in as_list(payload.get("source_statement_ids")) if s in answer_ids]
        return {
            **req,
            "statement": " ".join(str(payload["statement"]).split()),
            "acceptance_criteria": " ".join(str(payload.get("acceptance_criteria", req.get("acceptance_criteria", ""))).split()),
            "verification_method": payload.get("verification_method", req.get("verification_method", "Test")),
            "source_statement_ids": list(dict.fromkeys(req.get("source_statement_ids", []) + new_sources)),
            "version": int(req.get("version", 1)) + 1,
            "resolved": as_list(payload.get("resolved")),
            "unresolved": as_list(payload.get("unresolved")),
        }
