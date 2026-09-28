"""Coordinator agent — runs the multi-agent pipeline for a case study (brief point 4).

    python -m src.orchestrator --case erx_issuance
    python -m src.orchestrator --case all
    python -m src.orchestrator --case epcs_signing --resume
    python -m src.orchestrator --case erx_issuance --apply-decisions

Execution order, with the agent responsible for each step:

    intake            coordinator     mask PHI, quarantine injections, split documents into statements
    interviews        interaction     two interview rounds per stakeholder (simulated personas)
    extraction        extraction      requirements per stakeholder and per document, grounded in the KB
    classification    classification  multi-label categories; FR/NFR; final requirement ids
    conflicts         conflict        duplicates merged, contradictions flagged
    quality_v1        validation      first-draft 29148 audit -> findings
    clarification     clarification   failing requirements back to their stakeholders, revised (bounded)
    compliance        compliance      control mappings, gap proposals
    security_privacy  security        STRIDE threats, proposals for unmitigated threats
    risk              risk            risk register, risk levels
    validation        validation      final audit, critic, hallucination audit, confidence, escalation
    sdlc              sdlc            factor scores (two models), rules + MCDA, workflow
    documentation     documentation   SRS, stories, use cases, RTM, registers
    approval          approval        the human approval queue; SQLite store of record

The coordinator is the only component with privileged access to the blackboard: it
passes each agent what it needs and commits what the agent returns. The blackboard
is checkpointed after every step, so an interrupted run can resume (`--resume`).
Everything lands in outputs/cases/<id>/.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import load_pipeline, store
from .agents import (AgentContext, Blackboard, ClarificationAgent, ClassificationAgent, ComplianceAgent,
                     ConflictDetectionAgent, DocumentationAgent, HumanApprovalAgent, RequirementExtractionAgent,
                     RiskAnalysisAgent, SDLCSelectionAgent, SecurityPrivacyAgent, StakeholderInteractionAgent,
                     ValidationAgent)
from .agents.base import active
from .cases import case_ids, case_out_dir, load_case
from .knowledge import fingerprint, load_stakeholder_templates
from .security import Vault, mask, quarantine
from .simulation import SimulatedStakeholder

STEPS = ["intake", "interviews", "extraction", "classification", "conflicts", "quality_v1",
         "clarification", "compliance", "security_privacy", "risk", "validation", "sdlc",
         "documentation", "approval"]


def public_case(case: dict[str, Any]) -> dict[str, Any]:
    """What agents may see: no persona facts, no raw (unmasked) document text."""
    pub = copy.deepcopy(case)
    pub["stakeholders"] = [{"id": s["id"], "role": s["role"]} for s in case["stakeholders"]]
    pub["documents"] = [{"id": d["id"], "type": d["type"]} for d in case.get("documents", [])]
    return pub


def _paragraphs(text: str) -> list[str]:
    paras = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block or (block.startswith("#") and len(block.split()) < 8):
            continue
        paras.append(" ".join(line.strip() for line in block.splitlines()))
    return paras


class Coordinator:
    def __init__(self, case_id: str, client: Any = None, retriever: Any = None, embedder: Any = None,
                 run_dir: Path | None = None, include_live: bool = False) -> None:
        self.case = load_case(case_id)
        self.include_live = include_live
        self.cfg = load_pipeline()
        self.run_dir = run_dir or case_out_dir(case_id)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if client is None:
            from .llm import OllamaClient

            client = OllamaClient()
        self.client = client
        self.board = Blackboard()
        self.ctx = AgentContext(case=public_case(self.case), board=self.board, client=client,
                                run_dir=self.run_dir, cfg=self.cfg, retriever=retriever, embedder=embedder)
        self.templates = load_stakeholder_templates()
        self.vault = Vault()
        self.sims = {p["id"]: SimulatedStakeholder(p, client) for p in self.case["stakeholders"]}
        self.state_path = self.run_dir / "state.json"

    # -- persistence ----------------------------------------------------------------

    def checkpoint(self) -> None:
        self.board.put("vault_counters", self.vault.counters())
        self.board.put("unlocked", {sid: sorted(sim.unlocked) for sid, sim in self.sims.items()})
        self.state_path.write_text(json.dumps(self.board.to_dict(), indent=1, default=str), encoding="utf-8")

    def restore(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.board._data.update(data)
        self.vault.restore_counters(data.get("vault_counters", {}))
        for sid, facts in data.get("unlocked", {}).items():
            if sid in self.sims:
                self.sims[sid].unlock(facts)

    # -- the run ----------------------------------------------------------------------

    def run(self, resume: bool = False) -> dict[str, Any]:
        if resume and self.state_path.exists():
            self.restore()
        else:
            for stale in ("agent_log.jsonl", "decisions.jsonl"):
                (self.run_dir / stale).unlink(missing_ok=True)
        done = set(self.board.get("completed_steps", []))
        timings = self.board.get("timings", {})
        started = datetime.now(timezone.utc).isoformat()

        for step in STEPS:
            if step in done:
                continue
            self.ctx.step = step
            t0 = time.perf_counter()
            print(f"[{self.case['id']}] {step} ...", flush=True)
            result = getattr(self, f"step_{step}")()
            timings[step] = round(time.perf_counter() - t0, 1)
            if result:
                print(f"[{self.case['id']}]   {result}", flush=True)
            self.board.append("completed_steps", step)
            self.board.put("timings", timings)
            self.checkpoint()

        self.vault.save(self.run_dir / "vault.enc")
        self.export()
        manifest = self.manifest(started, timings)
        (self.run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    # -- intake -----------------------------------------------------------------------

    def _ingest(self, text: str, source: str) -> str:
        """Every piece of stakeholder text passes here before any agent sees it."""
        paras_out = []
        for para in text.split("\n\n"):
            masked, pii = mask(para, self.vault)
            clean, injections = quarantine(masked)
            for f in injections:
                self.ctx.security_event(
                    kind="prompt_injection" if f["severity"] == "high" else "suspicious_link",
                    source=source, detail=f["match"], pattern=f["kind"], sentence=f["sentence"][:240])
            if pii:
                self.ctx.security_event(kind="phi_masked", source=source,
                                        kinds=sorted({p["kind"] for p in pii}), count=len(pii))
            paras_out.append(clean)
        return "\n\n".join(paras_out)

    def step_intake(self) -> str:
        statements = []
        for doc in self.case.get("documents", []):
            clean = self._ingest(doc["text"], doc["id"])
            for k, para in enumerate(_paragraphs(clean), start=1):
                statements.append({"id": f"{doc['id']}#p{k}", "stakeholder": None, "role": doc["type"],
                                   "source_type": "document", "source_id": doc["id"], "text": para,
                                   "round": 0, "fact_ids": []})
        if self.include_live:
            statements.extend(self._live_statements())
        self.board.put("statements", statements)
        events = self.board.get("security_events", [])
        return (f"{len(statements)} document statements; "
                f"{sum(1 for e in events if e['kind'] == 'prompt_injection')} injection(s) quarantined; "
                f"{sum(e.get('count', 0) for e in events if e['kind'] == 'phi_masked')} identifier(s) masked")

    def _live_statements(self) -> list[dict[str, Any]]:
        """Transcripts of real people interviewed through the web UI (already masked there)."""
        out = []
        for k, path in enumerate(sorted((self.run_dir / "live_interviews").glob("*.json")), start=1):
            data = json.loads(path.read_text(encoding="utf-8"))
            sid = f"LIVE{k}"
            for n, s in enumerate(data.get("statements", []), start=1):
                out.append({**s, "id": f"S-{sid}-{n:02d}", "stakeholder": sid, "source_id": sid,
                            "text": self._ingest(s["text"], f"live:{sid}"), "fact_ids": []})
        return out

    # -- interviews -------------------------------------------------------------------

    def _add_answers(self, persona: dict[str, Any], questions: list[dict[str, Any]],
                     answers: list[dict[str, Any]], round_label: Any) -> list[dict[str, Any]]:
        statements = self.board.get("statements", [])
        n = sum(1 for s in statements if s.get("stakeholder") == persona["id"])
        by_q = {a["question_id"]: a for a in answers}
        new = []
        for q in questions:
            a = by_q.get(q["id"])
            if not a:
                continue
            n += 1
            new.append({"id": f"S-{persona['id']}-{n:02d}", "stakeholder": persona["id"],
                        "role": persona["role"], "source_type": "interview", "source_id": persona["id"],
                        "round": round_label, "topic": q.get("topic", ""), "question": q["question"],
                        "text": self._ingest(a["answer"], f"interview:{persona['id']}"),
                        "follows_up": q.get("about_statement", ""), "about_requirement": q.get("req_id", ""),
                        "fact_ids": a.get("fact_ids", [])})
        statements.extend(new)
        self.board.put("statements", statements)
        return new

    @staticmethod
    def _public(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in s.items() if k != "fact_ids"} for s in statements]

    def step_interviews(self) -> str:
        agent = StakeholderInteractionAgent(self.ctx, self.templates)
        log = []
        for p in self.case["stakeholders"]:
            sim = self.sims[p["id"]]
            who = {"id": p["id"], "role": p["role"]}
            questions = agent.plan_questions(who)
            first = self._add_answers(p, questions, sim.answer(questions, self.case["id"]), 1)
            issues = agent.detect_issues(self._public(first))
            followups = []
            if self.cfg["agents"]["interview_rounds"] > 1 and first:
                followups = agent.plan_followups(who, self._public(first), issues)
                by_id = {s["id"]: s for s in first}
                for f in followups:
                    # Harness: a follow-up aimed at a statement unlocks the facts behind it.
                    sim.unlock(by_id.get(f["about_statement"], {}).get("fact_ids", []))
                self._add_answers(p, followups, sim.answer(followups, self.case["id"]), 2)
            log.append({"stakeholder": p["id"], "role": p["role"], "questions": questions,
                        "rule_issues": issues, "followups": followups})
        self.board.put("interview_log", log)
        n = sum(1 for s in self.board.get("statements", []) if s["source_type"] == "interview")
        return f"{n} interview statements; {sum(len(x['followups']) for x in log)} follow-ups"

    # -- extraction and classification --------------------------------------------------

    def step_extraction(self) -> str:
        agent = RequirementExtractionAgent(self.ctx)
        statements = self._public(self.board.get("statements", []))
        drafts, out_of_scope, failures = [], [], 0
        people = [(p["id"], p["role"]) for p in self.case["stakeholders"]]
        people += sorted({(s["stakeholder"], s["role"]) for s in statements
                          if str(s.get("stakeholder") or "").startswith("LIVE")})
        sources = [(f"stakeholder {role} ({sid})", "stakeholder",
                    [s for s in statements if s.get("stakeholder") == sid]) for sid, role in people]
        sources += [(f"document {d['id']} ({d['type']})", "document",
                     [s for s in statements if s.get("source_id") == d["id"] and s["source_type"] == "document"])
                    for d in self.case.get("documents", [])]
        for label, origin, group in sources:
            if not group:
                continue
            reqs, errors, oos = agent.extract(label, group)
            failures += bool(errors) and not reqs
            for r in reqs:
                r["origin"] = origin
            drafts.extend(reqs)
            out_of_scope.extend(oos)
        for i, d in enumerate(drafts, start=1):
            d["tmp_id"] = f"T-{i:03d}"
        self.board.put("drafts", drafts)
        self.board.put("out_of_scope", sorted(set(out_of_scope)))
        return f"{len(drafts)} draft requirements from {len(sources)} sources ({failures} source(s) failed)"

    def _assign_ids(self, reqs: list[dict[str, Any]]) -> None:
        prefix = self.case.get("id_prefix", "REQ")
        existing = self.board.get("requirements", [])
        counters = {"FR": 0, "NFR": 0}
        for r in existing:
            kind, _, num = r["req_id"].partition(f"-{prefix}-")
            if kind in counters and num.isdigit():
                counters[kind] = max(counters[kind], int(num))
        for r in reqs:
            counters[r["type"]] += 1
            r["req_id"] = f"{r['type']}-{prefix}-{counters[r['type']]:03d}"
            r.setdefault("version", 1)
            r.setdefault("status", "active")
            r.setdefault("approval_status", "pending")
            r.pop("tmp_id", None)

    def _classify_and_number(self, reqs: list[dict[str, Any]]) -> None:
        agent = ClassificationAgent(self.ctx)
        for i, r in enumerate(reqs, start=1):
            r["tmp_id"] = f"T-{i:03d}"
        cats = agent.classify(reqs, key="tmp_id")
        for r in reqs:
            preset = r.get("categories")
            agent.apply(r, list(dict.fromkeys((preset or []) + cats[r["tmp_id"]])))
        self._assign_ids(reqs)

    def step_classification(self) -> str:
        drafts = self.board.get("drafts", [])
        self._classify_and_number(drafts)
        self.board.put("requirements", drafts)
        self.board.put("requirement_history", [{"req_id": r["req_id"], "event": "created", "version": 1,
                                                "origin": r["origin"]} for r in drafts])
        n_fr = sum(1 for r in drafts if r["type"] == "FR")
        return f"{len(drafts)} requirements ({n_fr} FR / {len(drafts) - n_fr} NFR)"

    # -- analysis -------------------------------------------------------------------------

    def step_conflicts(self) -> str:
        return str(ConflictDetectionAgent(self.ctx).run())

    def step_quality_v1(self) -> str:
        snap = ValidationAgent(self.ctx).check_quality("v1", 0)
        return f"first-draft mean 29148 pass rate {snap.get('mean_pass_rate')}"

    def step_clarification(self) -> str:
        clar = ClarificationAgent(self.ctx)
        extraction = RequirementExtractionAgent(self.ctx)
        validation = ValidationAgent(self.ctx)
        stakeholders = public_case(self.case)["stakeholders"]
        personas = {p["id"]: p for p in self.case["stakeholders"]}
        revised_total = 0
        for rnd in range(1, self.cfg["agents"]["clarification_rounds"] + 1):
            plan = clar.plan(stakeholders, rnd)
            if not plan:
                break
            statements = {s["id"]: s for s in self.board.get("statements", [])}
            entries = []
            for sid, questions in plan.items():
                sim = self.sims.get(sid)
                if sim is None:
                    # A live interviewee is not available to answer now; the finding
                    # stays open and is escalated with the requirement.
                    entries += [{"round": rnd, "req_id": q["req_id"], "stakeholder": sid, "question": q["question"],
                                 "issues": q["issues"], "answer_statement": "", "revised": False} for q in questions]
                    continue
                reqs = {r["req_id"]: r for r in self.board.get("requirements", [])}
                for q in questions:
                    for st in reqs[q["req_id"]].get("source_statement_ids", []):
                        if statements.get(st, {}).get("stakeholder") == sid:
                            sim.unlock(statements[st].get("fact_ids", []))
                answers = sim.answer(questions, self.case["id"])
                new = self._add_answers(personas[sid], questions, answers, f"c{rnd}")
                by_q = {s["about_requirement"]: s for s in new}
                for q in questions:
                    req = reqs[q["req_id"]]
                    answer = by_q.get(q["req_id"])
                    open_issues = [f"{f['kind']}: {f['detail']}" for f in self.board.get("findings", [])
                                   if f["req_id"] == req["req_id"] and not f.get("resolved")
                                   and f["kind"] in {"ambiguity", "incomplete", "untestable",
                                                     "missing_source", "undefined_term"}]
                    revised = extraction.revise(req, open_issues, self._public([answer])) if answer else None
                    if revised:
                        reqs[req["req_id"]].update(revised)
                        self.board.append("requirement_history", {
                            "req_id": req["req_id"], "event": "clarified", "round": rnd,
                            "version": revised["version"], "answer": answer["id"]})
                        revised_total += 1
                    entries.append({"round": rnd, "req_id": q["req_id"], "stakeholder": sid,
                                    "question": q["question"], "issues": q["issues"],
                                    "answer_statement": answer["id"] if answer else "", "revised": bool(revised)})
                self.board.put("requirements", list(reqs.values()))
            clar.record(entries)
            validation.check_quality(f"after_clarification_{rnd}", rnd)
        remaining = sum(len(v) for v in clar.open_issues().values())
        return f"{revised_total} revision(s); {remaining} clarifiable finding(s) still open"

    def step_compliance(self) -> str:
        agent = ComplianceAgent(self.ctx)
        mapped = agent.map_requirements()
        proposals = agent.propose_gaps()
        if proposals:
            self._classify_and_number(proposals)
            agent.commit_proposals(proposals)
        open_gaps = sum(1 for g in self.board.get("gaps", []) if g["status"] == "open")
        return f"{mapped}; {len(proposals)} gap proposal(s); {open_gaps} gap(s) still open"

    def step_security_privacy(self) -> str:
        agent = SecurityPrivacyAgent(self.ctx)
        proposals = agent.analyse()
        if proposals:
            self._classify_and_number(proposals)
            agent.commit_proposals(proposals)
        return f"{len(self.board.get('threats', []))} threat(s); {len(proposals)} proposal(s)"

    def step_risk(self) -> str:
        return str(RiskAnalysisAgent(self.ctx).run())

    def step_validation(self) -> str:
        return str(ValidationAgent(self.ctx).final(critic=self.cfg["agents"].get("critic", True)))

    def step_sdlc(self) -> str:
        return str(SDLCSelectionAgent(self.ctx).run())

    def step_documentation(self) -> str:
        return f"{len(DocumentationAgent(self.ctx).run())} artefact(s) written"

    def step_approval(self) -> str:
        result = HumanApprovalAgent(self.ctx).run()
        store.save(self.run_dir, self.board.to_dict(), fresh=True)
        return str(result)

    # -- outputs ---------------------------------------------------------------------------

    def export(self) -> None:
        from .agents.validation import to_frame

        reqs = active(self.board.get("requirements", []))
        if reqs:
            to_frame(reqs).to_csv(self.run_dir / "requirements.csv", index=False, encoding="utf-8")
        pd.DataFrame(self._public(self.board.get("statements", []))).to_csv(
            self.run_dir / "statements.csv", index=False, encoding="utf-8")
        pd.DataFrame(self.board.get("findings", [])).to_csv(self.run_dir / "findings.csv", index=False, encoding="utf-8")
        pd.DataFrame(self.board.get("security_events", [])).to_csv(
            self.run_dir / "security_events.csv", index=False, encoding="utf-8")
        pd.DataFrame(self.board.get("approvals", [])).to_csv(
            self.run_dir / "review_queue.csv", index=False, encoding="utf-8")

    def manifest(self, started: str, timings: dict[str, float]) -> dict[str, Any]:
        digests = self.client.model_digests() if hasattr(self.client, "model_digests") else {}
        models = self.cfg["agents"]
        return {
            "case": self.case["id"], "started": started, "finished": datetime.now(timezone.utc).isoformat(),
            "seconds_total": round(sum(timings.values()), 1), "seconds_by_step": timings,
            "agent_model": models["model"], "persona_model": models["persona_model"],
            "model_digests": digests, "knowledge_base": fingerprint(),
            "requirements": len(active(self.board.get("requirements", []))),
            "approval_items": len(self.board.get("approvals", [])),
            "security_events": len(self.board.get("security_events", [])),
        }

    # -- after human review -------------------------------------------------------------------

    def apply_decisions(self) -> dict[str, int]:
        """Apply recorded human decisions to the requirement set and regenerate the artefacts.

        accept -> approved; reject -> rejected (removed from the baseline); modify ->
        the reviewer's text becomes a new version, approved; regenerate -> the extraction
        agent revises the requirement using the reviewer's note, and it goes back into the
        queue as a new pending item.
        """
        self.restore()
        decided = store.decisions(self.run_dir)
        reqs = {r["req_id"]: r for r in self.board.get("requirements", [])}
        extraction = RequirementExtractionAgent(self.ctx)
        queue = self.board.get("approvals", [])
        by_id = {q["id"]: q for q in queue}
        counts = {"accepted": 0, "rejected": 0, "modified": 0, "regenerated": 0}
        for _, d in decided.iterrows():
            item = by_id.get(d["approval_id"])
            if item is None:
                continue
            item.update(status=store.DECISIONS[d["decision"]], decision=d["decision"],
                        decided_by=d["user"], decided_at=d["at"], note=d["note"], modified_text=d["modified_text"])
            if item["item_type"] != "requirement_baseline" or d["item_id"] not in reqs:
                continue
            req = reqs[d["item_id"]]
            if d["decision"] == "accept":
                req["approval_status"] = "approved"
                counts["accepted"] += 1
            elif d["decision"] == "reject":
                req["approval_status"] = "rejected"
                req["status"] = "rejected"
                counts["rejected"] += 1
            elif d["decision"] == "modify":
                req.update(statement=d["modified_text"], version=int(req.get("version", 1)) + 1,
                           approval_status="approved (modified)")
                counts["modified"] += 1
            elif d["decision"] == "regenerate":
                self.ctx.step = "regenerate"
                revised = extraction.revise(req, [f"reviewer: {d['note']}"], [], tag="regenerate")
                if revised:
                    req.update(revised)
                    req["approval_status"] = "pending"
                    queue.append({**item, "id": f"APR-{len(queue) + 1:03d}", "status": "pending", "decision": "",
                                  "decided_by": "", "decided_at": "", "note": "",
                                  "reason": f"regenerated after review: {d['note']}", "modified_text": ""})
                    counts["regenerated"] += 1
            self.board.append("requirement_history", {"req_id": req["req_id"], "event": f"human_{d['decision']}",
                                                      "by": d["user"], "role": d["role"], "version": req.get("version")})
        self.board.put("requirements", list(reqs.values()))
        self.board.put("approvals", queue)
        self.ctx.step = "documentation"
        DocumentationAgent(self.ctx).run(llm=False)
        store.save(self.run_dir, self.board.to_dict(), fresh=False)
        self.checkpoint()
        self.export()
        return counts


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the multi-agent requirements pipeline on a case study")
    ap.add_argument("--case", required=True, help=f"case id or 'all' ({', '.join(case_ids())})")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted run from its last step")
    ap.add_argument("--apply-decisions", action="store_true",
                    help="apply the recorded human decisions and regenerate the artefacts")
    ap.add_argument("--include-live", action="store_true",
                    help="also extract from interviews recorded through the web UI")
    args = ap.parse_args()

    for cid in case_ids() if args.case == "all" else [args.case]:
        coordinator = Coordinator(cid, include_live=args.include_live)
        if args.apply_decisions:
            print(f"[{cid}] applied decisions: {coordinator.apply_decisions()}")
            continue
        manifest = coordinator.run(resume=args.resume)
        print(f"\n[{cid}] done in {manifest['seconds_total']}s: {manifest['requirements']} requirements, "
              f"{manifest['approval_items']} approval items -> {coordinator.run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
