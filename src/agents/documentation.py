"""Documentation agent (brief point 12).

Generates the requirement artefacts for a case under outputs/cases/<id>/artifacts/:

    srs.md                       Software Requirements Specification (ISO/IEC/IEEE 29148 outline)
    user_stories.md              user stories with Gherkin acceptance scenarios
    use_cases.md                 key use cases; process_workflow.md renders the first as a flow
    data_requirements.md         requirements about data content and retention
    interface_requirements.md    requirements about exchange with other systems
    sdlc_recommendation.md       ranked SDLC recommendation, rules, explanation, workflow
    rtm.csv                      requirements traceability matrix
    compliance_matrix.csv        requirement x control mappings and open gaps
    risk_register.csv, threat_register.csv
    assumptions_dependencies.csv, open_issues.csv

Everything except the stories and use cases is assembled deterministically from the
blackboard, so every artefact stays linked to the stakeholder statements, corpus
chunks and controls behind each requirement.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..knowledge import applicable_controls, controls_by_id
from .base import Agent, active, as_list, items

SECTION_ORDER = ["functional", "performance", "usability", "security", "privacy", "regulatory",
                 "availability_reliability", "data_management", "integration", "audit_reporting",
                 "operational", "business", "stakeholder"]
TITLES = {"functional": "Functional requirements", "performance": "Performance requirements",
          "usability": "Usability requirements", "security": "Security requirements",
          "privacy": "Privacy requirements", "regulatory": "Regulatory requirements",
          "availability_reliability": "Availability and reliability requirements",
          "data_management": "Data requirements", "integration": "Interface and integration requirements",
          "audit_reporting": "Audit and reporting requirements", "operational": "Operational requirements",
          "business": "Business requirements", "stakeholder": "Stakeholder requirements"}


def _primary(req: dict[str, Any]) -> str:
    cats = req.get("categories") or ["functional"]
    return min(cats, key=lambda c: SECTION_ORDER.index(c) if c in SECTION_ORDER else 99)


def _cell(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return "" if value is None else str(value)


class DocumentationAgent(Agent):
    name = "documentation"

    def run(self, llm: bool = True) -> dict[str, str]:
        out = self.ctx.run_dir / "artifacts"
        out.mkdir(parents=True, exist_ok=True)
        reqs = self.read("requirements", [])
        live = active(reqs)
        statements = {s["id"]: s for s in self.read("statements", [])}
        written: dict[str, str] = {}

        def save(name: str, content: str | pd.DataFrame) -> None:
            path = out / name
            if isinstance(content, pd.DataFrame):
                content.to_csv(path, index=False, encoding="utf-8")
            else:
                path.write_text(content, encoding="utf-8")
            written[name] = str(path)

        stories = self._stories(live) if llm else {}
        use_cases = self._use_cases(live) if llm else []

        save("srs.md", self._srs(live, statements))
        save("rtm.csv", self._rtm(live, statements))
        save("compliance_matrix.csv", self._compliance_matrix())
        save("risk_register.csv", pd.DataFrame(self.read("risks", [])))
        save("threat_register.csv", pd.DataFrame([{**t, "mitigated_by": _cell(t.get("mitigated_by"))}
                                                  for t in self.read("threats", [])]))
        save("assumptions_dependencies.csv", self._assumptions(live))
        save("open_issues.csv", self._open_issues(live))
        save("data_requirements.md", self._subset(live, "data_management", "Data requirements"))
        save("interface_requirements.md", self._subset(live, "integration", "Interface requirements"))
        save("sdlc_recommendation.md", self._sdlc())
        save("user_stories.md", self._stories_md(live, stories))
        save("use_cases.md", self._use_cases_md(use_cases))
        save("process_workflow.md", self._process(use_cases))

        index = self.read("artifacts", {}) or {}
        index.update(written)
        self.write("artifacts", index)
        return written

    # -- SRS ----------------------------------------------------------------------

    def _srs(self, live: list[dict[str, Any]], statements: dict[str, dict[str, Any]]) -> str:
        case = self.ctx.case
        fn = case["functionality"]
        roles = sorted({s.get("role", "") for s in statements.values() if s.get("source_type") == "interview"})
        refs = sorted({c["citation"] for c in applicable_controls(case)})
        lines = [
            f"# Software Requirements Specification — {fn['name']}", "",
            "_Generated by the documentation agent. Every requirement below is pending human "
            "approval; see the approval queue for its status._", "",
            "## 1. Introduction", "",
            "### 1.1 Purpose", "",
            f"This specification states the requirements for {fn['name'].lower()} as elicited from "
            f"{len(roles)} stakeholder roles and {len(case.get('documents', []))} project documents, "
            "grounded in the authorised knowledge base.", "",
            "### 1.2 Scope", "", fn["description"].strip(), "",
        ]
        oos = self.read("out_of_scope", [])
        if oos:
            lines += ["Out of scope:", ""] + [f"- {o}" for o in oos] + [""]
        lines += ["### 1.3 User classes", ""] + [f"- {r.replace('_', ' ')}" for r in roles] + [""]
        lines += ["### 1.4 References", ""] + [f"- {r}" for r in refs] + [""]
        lines += ["## 2. Requirements", ""]

        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in live:
            grouped.setdefault(_primary(r), []).append(r)
        n = 0
        for section in SECTION_ORDER:
            group = grouped.get(section)
            if not group:
                continue
            n += 1
            lines += [f"### 2.{n} {TITLES[section]}", ""]
            for r in sorted(group, key=lambda x: x["req_id"]):
                lines += self._req_block(r, statements)
        lines += ["## 3. Verification", "",
                  "| Requirement | Method | Acceptance criteria |", "|---|---|---|"]
        lines += [f"| {r['req_id']} | {r.get('verification_method', '')} | "
                  f"{r.get('acceptance_criteria', '').replace('|', '/')} |" for r in live]
        lines += ["", "## 4. Traceability", "",
                  "The requirements traceability matrix is `rtm.csv`: stakeholder statement → "
                  "requirement → evidence chunk → control → acceptance criterion → approval.", ""]
        return "\n".join(lines)

    @staticmethod
    def _req_block(r: dict[str, Any], statements: dict[str, dict[str, Any]]) -> list[str]:
        who = sorted({statements[s].get("role", "document") for s in r.get("source_statement_ids", [])
                      if s in statements})
        esc = f" — **escalated:** {r['confidence_reasons']}" if r.get("escalate") else ""
        return [
            f"**{r['req_id']}** (v{r.get('version', 1)}, {r.get('origin', 'stakeholder')}) — {r['statement']}", "",
            f"- Acceptance criteria: {r.get('acceptance_criteria', '') or '—'}",
            f"- Verification: {r.get('verification_method', '')}; priority {r.get('priority', '')}; "
            f"risk {r.get('risk_level', r.get('risk_class', ''))}; volatility {r.get('volatility', '')}",
            f"- Categories: {', '.join(r.get('categories', []))}",
            f"- Sources: {', '.join(r.get('source_statement_ids', [])) or '—'}"
            + (f" ({', '.join(x.replace('_', ' ') for x in who)})" if who else ""),
            f"- Evidence: {', '.join(r.get('source_chunk_ids', [])) or '—'}; "
            f"regulations: {', '.join(r.get('regulations', [])) or '—'}",
            f"- Confidence: {r.get('confidence', '—')}; approval: {r.get('approval_status', 'pending')}{esc}",
            "",
        ]

    # -- registers ----------------------------------------------------------------

    def _rtm(self, live: list[dict[str, Any]], statements: dict[str, dict[str, Any]]) -> pd.DataFrame:
        rows = []
        for r in live:
            rows.append({
                "req_id": r["req_id"], "version": r.get("version", 1), "statement": r["statement"],
                "origin": r.get("origin", ""),
                "stakeholder_statements": _cell(r.get("source_statement_ids")),
                "stakeholder_roles": _cell(sorted({statements[s].get("role", "") for s in
                                                   r.get("source_statement_ids", []) if s in statements})),
                "source_documents": _cell(sorted({statements[s].get("source_id", "") for s in
                                                  r.get("source_statement_ids", []) if s in statements
                                                  and statements[s].get("source_type") == "document"})),
                "evidence_chunks": _cell(r.get("source_chunk_ids")),
                "controls": _cell(r.get("control_ids")), "regulations": _cell(r.get("regulations")),
                "acceptance_criteria": r.get("acceptance_criteria", ""),
                "verification_method": r.get("verification_method", ""),
                "confidence": r.get("confidence"), "approval_status": r.get("approval_status", "pending"),
            })
        return pd.DataFrame(rows)

    def _compliance_matrix(self) -> pd.DataFrame:
        rows = list(self.read("compliance", []))
        catalogue = controls_by_id()
        for g in self.read("gaps", []):
            if g["status"] == "open":
                c = catalogue.get(g["control_id"], {})
                rows.append({"req_id": "", "control_id": g["control_id"], "citation": c.get("citation", ""),
                             "relation": "GAP", "evidence_chunk_id": "", "rationale": "no requirement covers this control",
                             "similarity": None, "needs_officer_approval": True, "status": "open"})
        return pd.DataFrame(rows)

    @staticmethod
    def _assumptions(live: list[dict[str, Any]]) -> pd.DataFrame:
        rows = []
        for r in live:
            rows += [{"req_id": r["req_id"], "kind": "assumption", "text": a} for a in r.get("assumptions", [])]
            rows += [{"req_id": r["req_id"], "kind": "dependency", "text": d} for d in r.get("dependencies", [])]
        return pd.DataFrame(rows, columns=["req_id", "kind", "text"])

    def _open_issues(self, live: list[dict[str, Any]]) -> pd.DataFrame:
        rows = []
        live_ids = {r["req_id"] for r in live}
        for f in self.read("findings", []):
            if not f.get("resolved") and f["req_id"] in live_ids:
                rows.append({"kind": f["kind"], "item": f["req_id"], "detail": f["detail"]})
        for c in self.read("conflicts", []):
            if c.get("status") == "open":
                rows.append({"kind": "conflict", "item": f"{c['req_a']} vs {c['req_b']}", "detail": c["explanation"]})
        for g in self.read("gaps", []):
            if g["status"] == "open":
                rows.append({"kind": "compliance_gap", "item": g["control_id"], "detail": "no requirement covers it"})
        for t in self.read("threats", []):
            if not t.get("mitigated_by") and not t.get("proposed_req_id"):
                rows.append({"kind": "unmitigated_threat", "item": t["id"], "detail": t["description"]})
        for e in self.read("security_events", []):
            rows.append({"kind": f"security:{e.get('kind')}", "item": e.get("source", e.get("agent", "")),
                         "detail": e.get("detail", e.get("kinds", ""))})
        for r in live:
            if r.get("escalate"):
                rows.append({"kind": "low_confidence", "item": r["req_id"], "detail": r.get("confidence_reasons", "")})
        return pd.DataFrame(rows, columns=["kind", "item", "detail"])

    @staticmethod
    def _subset(live: list[dict[str, Any]], category: str, title: str) -> str:
        chosen = [r for r in live if category in r.get("categories", [])]
        lines = [f"# {title}", "", "| Requirement | Statement | Acceptance criteria | Sources |", "|---|---|---|---|"]
        lines += [f"| {r['req_id']} | {r['statement']} | {r.get('acceptance_criteria', '')} | "
                  f"{_cell(r.get('source_statement_ids') or r.get('source_chunk_ids'))} |" for r in chosen]
        return "\n".join(lines) + "\n"

    def _sdlc(self) -> str:
        s = self.read("sdlc", {}) or {}
        rec = s.get("recommendation")
        if not rec:
            return "# SDLC recommendation\n\nNot produced: " + str(s.get("reason", "the SDLC step did not run")) + "\n"
        lines = ["# SDLC recommendation", "",
                 f"**Recommended:** {rec['top']} ({rec['ranking'][0]['pct']}%) — runner-up {rec['runner_up']}. "
                 "Status: pending approval by " + ", ".join(r.replace('_', ' ') for r in s["approval_roles"]) + ".", "",
                 "| Rank | Model | Suitability | Supporting rules |", "|---|---|---|---|"]
        lines += [f"| {i} | {r['model']} | {r['pct']}% | {', '.join(r['rule_support']) or '—'} |"
                  for i, r in enumerate(rec["ranking"], start=1)]
        lines += ["", "## Decision factors (median of both models)", "", "| Factor | Score |", "|---|---|"]
        lines += [f"| {f} | {v:g} |" for f, v in s["aggregate"].items()]
        if s.get("contested_factors"):
            lines += ["", "Contested (models differ by 2+ points): " + ", ".join(s["contested_factors"])]
        if rec["cautions"]:
            lines += ["", "## Cautions", ""] + [f"- {c}" for c in rec["cautions"]]
        if rec["escalate"]:
            lines += ["", "**Escalated:** " + "; ".join(rec["escalation_reasons"])]
        exp = s.get("explanation", {})
        lines += ["", "## Justification", "", exp.get("explanation", "") or "_No explanation produced._", ""]
        if exp.get("strongest_counterargument"):
            lines += [f"Strongest argument against: {exp['strongest_counterargument']}", ""]
        lines += ["", s.get("workflow_markdown", ""), "", "```mermaid", s.get("workflow_mermaid", ""), "```", ""]
        tailored = [(p["name"], a) for p in s.get("workflow", []) for a in p.get("tailored", [])]
        if tailored:
            lines += ["## Project-specific activities", ""] + [f"- **{n}:** {a}" for n, a in tailored]
        return "\n".join(lines) + "\n"

    # -- LLM-written artefacts -------------------------------------------------------

    def _stories(self, live: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        frs = [r for r in live if r.get("type") == "FR"]
        out: dict[str, dict[str, Any]] = {}
        size = self.ctx.cfg["agents"]["batch_size"]
        for start in range(0, len(frs), size):
            batch = frs[start:start + size]
            ids = {r["req_id"] for r in batch}

            def check(p: Any, ids=ids) -> list[str]:
                got = {x.get("req_id") for x in items(p, "stories")}
                errs = [f"no story for {rid}" for rid in sorted(ids - got)]
                errs += [f"{x.get('req_id')}: story must start 'As a'" for x in items(p, "stories")
                         if not str(x.get("story", "")).strip().lower().startswith("as a")]
                return errs

            payload, _ = self.ask(
                "user_stories",
                {"REQUIREMENTS": "\n".join(f"{r['req_id']} | {r.get('actor', '')} | {r['statement']} | "
                                           f"{r.get('acceptance_criteria', '')}" for r in batch)},
                check, tag=f"stories.{start // size + 1}",
            )
            for x in items(payload, "stories"):
                if x.get("req_id") in ids:
                    out[x["req_id"]] = {"story": str(x.get("story", "")), "scenarios": as_list(x.get("scenarios"))
                                        if isinstance(x.get("scenarios"), list) else [str(x.get("scenarios", ""))]}
        return out

    def _use_cases(self, live: list[dict[str, Any]]) -> list[dict[str, Any]]:
        frs = [r for r in live if r.get("type") == "FR"]
        if not frs:
            return []
        ids = {r["req_id"] for r in frs}
        fn = self.ctx.case["functionality"]

        def check(p: Any) -> list[str]:
            ucs = items(p, "use_cases")
            errs = [] if ucs else ["'use_cases' must list at least one use case"]
            errs += [f"{u.get('id')}: main_flow must be a list of steps" for u in ucs
                     if not isinstance(u.get("main_flow"), list) or not u["main_flow"]]
            return errs

        payload, _ = self.ask(
            "use_cases",
            {"FUNCTIONALITY": f"{fn['name']}\n{fn['description'].strip()}",
             "REQUIREMENTS": "\n".join(f"{r['req_id']}: {r['statement']}" for r in frs),
             "N": str(self.ctx.cfg["agents"].get("use_cases", 4))},
            check, tag="use_cases",
        )
        ucs = []
        for u in items(payload, "use_cases"):
            if isinstance(u.get("main_flow"), list) and u["main_flow"]:
                u["req_ids"] = [x for x in as_list(u.get("req_ids")) if x in ids]
                ucs.append(u)
        return ucs

    @staticmethod
    def _stories_md(live: list[dict[str, Any]], stories: dict[str, dict[str, Any]]) -> str:
        lines = ["# User stories", ""]
        for r in live:
            s = stories.get(r["req_id"])
            if not s:
                continue
            lines += [f"## {r['req_id']}", "", s["story"], "", "```gherkin"] + s["scenarios"] + ["```", ""]
        if len(lines) == 2:
            lines.append("_No user stories were generated._")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _use_cases_md(ucs: list[dict[str, Any]]) -> str:
        lines = ["# Use cases", ""]
        for u in ucs:
            pre = u.get("preconditions") or []
            pre = pre if isinstance(pre, list) else [pre]
            lines += [f"## {u.get('id', '')} {u.get('name', '')}", "",
                      f"- Primary actor: {u.get('primary_actor', '')}",
                      f"- Realises: {', '.join(u.get('req_ids', []))}",
                      "- Preconditions: " + ("; ".join(str(p) for p in pre) or "none"),
                      "", "Main success scenario:", ""]
            lines += [f"{i}. {step}" for i, step in enumerate(u["main_flow"], start=1)]
            alt = u.get("alternate_flows") or []
            if alt:
                lines += ["", "Alternate and exception flows:", ""] + [f"- {a}" for a in alt]
            post = u.get("postconditions") or []
            if post:
                lines += ["", "Postconditions: " + "; ".join(str(p) for p in post)]
            lines.append("")
        if len(lines) == 2:
            lines.append("_No use cases were generated._")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _process(ucs: list[dict[str, Any]]) -> str:
        if not ucs:
            return "# Process workflow\n\n_No use case was available to derive the process from._\n"
        u = ucs[0]
        lines = [f"# Process workflow — {u.get('name', '')}", "",
                 "Derived from the main success scenario of the first use case.", "", "```mermaid", "flowchart TD"]
        for i, step in enumerate(u["main_flow"]):
            label = str(step).replace('"', "'")[:80]
            lines.append(f'    S{i}["{label}"]')
            if i:
                lines.append(f"    S{i-1} --> S{i}")
        lines += ["```", ""]
        return "\n".join(lines)
