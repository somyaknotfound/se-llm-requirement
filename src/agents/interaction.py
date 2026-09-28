"""Stakeholder-interaction agent: adaptive interviews (brief points 2 and 7).

Round 1 asks role-specific questions generated from the interview templates in
config/stakeholders.yaml, adapted to the case. Round 2 follows up on answers that
are vague, incomplete or inconsistent. Rule checks find the obvious cases — a
weak word, or no number where the topic needs one — and every rule-flagged answer
gets a follow-up even if the model does not propose one.
"""

from __future__ import annotations

import re
from typing import Any

from ..security import spotlight
from .base import Agent, expect_list, items

# Words that make an answer too vague to turn into a testable requirement. The
# validation weak-word list plus conversational ones interviews produce.
EXTRA_VAGUE = ["quick", "fast", "promptly", "regularly", "soon", "secure", "clear",
               "enough", "too many", "all the time", "keep an eye", "as required",
               "required period", "take long", "early enough", "as little as possible",
               "able to trust", "able to help", "help with", "as the dea requires"]
NO_ANSWER = re.compile(r"\b(don't know|do not know|not sure|not my area|no idea)\b", re.I)


class StakeholderInteractionAgent(Agent):
    name = "stakeholder_interaction"

    def __init__(self, ctx, templates: dict[str, Any]) -> None:
        super().__init__(ctx)
        self.templates = templates
        weak = ctx.cfg["validation"]["weak_words"]
        self.vague_words = sorted(set(weak) | set(EXTRA_VAGUE), key=len, reverse=True)

    def _functionality(self) -> str:
        fn = self.ctx.case["functionality"]
        return f"{fn['name']}\n{fn['description'].strip()}"

    def plan_questions(self, stakeholder: dict[str, Any]) -> list[dict[str, str]]:
        role = stakeholder["role"]
        topics = self.templates["roles"][role]["topics"]
        topic_lines = "\n".join(
            f"{t} | {self.templates['topics'][t]['label']} | {self.templates['topics'][t]['seed']}"
            for t in topics
        )
        n = self.ctx.cfg["agents"]["questions_per_role"]

        def check(p: Any) -> list[str]:
            errs = expect_list(p, "questions", 3)
            for i, q in enumerate(items(p, "questions"), 1):
                if not str(q.get("question", "")).strip():
                    errs.append(f"question {i} is empty")
            return errs

        payload, _ = self.ask(
            "interview_questions",
            {"FUNCTIONALITY": self._functionality(),
             "STAKEHOLDER": f"{self.templates['roles'][role]['label']} ({role})",
             "TOPICS": topic_lines, "N": str(n)},
            check, tag=f"questions.{stakeholder['id']}",
        )
        qs = [q for q in items(payload, "questions") if str(q.get("question", "")).strip()]
        if not qs:
            # The interview must go on: fall back to the template's seed questions.
            qs = [{"topic": t, "question": self.templates["topics"][t]["seed"]} for t in topics]
            self.ctx.log(self.name, "fallback_seed_questions", stakeholder=stakeholder["id"])
        return [
            {"id": f"Q{i}", "topic": q.get("topic") if q.get("topic") in topics else "",
             "question": str(q["question"]).strip()}
            for i, q in enumerate(qs[: n + 2], start=1)
        ]

    def detect_issues(self, statements: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Rule checks on answers: vague wording, or no number where one is needed."""
        issues = []
        for s in statements:
            text = s["text"]
            if NO_ANSWER.search(text):
                continue
            low = text.lower()
            vague = [w for w in self.vague_words if re.search(rf"\b{re.escape(w)}\b", low)]
            quantitative = self.templates["topics"].get(s.get("topic", ""), {}).get("quantitative")
            if vague:
                issues.append({"statement_id": s["id"], "issue": "vague",
                               "detail": "vague wording: " + ", ".join(vague[:3])})
            elif quantitative and not re.search(r"\d", text):
                issues.append({"statement_id": s["id"], "issue": "incomplete",
                               "detail": "no number given for a topic that needs one"})
        return issues

    def plan_followups(
        self, stakeholder: dict[str, Any], statements: list[dict[str, Any]], issues: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        ids = {s["id"] for s in statements}
        block = spotlight(
            "\n".join(f"{s['id']} | {s.get('question', '')} | {s['text']}" for s in statements),
            f"interview:{stakeholder['id']}",
        )
        issue_lines = "\n".join(f"{i['statement_id']}: {i['issue']} ({i['detail']})" for i in issues) or "none"
        n = max(3, len(issues))

        def check(p: Any) -> list[str]:
            errs = expect_list(p, "followups", 0)
            for f in items(p, "followups"):
                if f.get("about_statement") not in ids:
                    errs.append(f"about_statement {f.get('about_statement')!r} is not one of the statement ids")
            return errs

        payload, _ = self.ask(
            "interview_followups",
            {"FUNCTIONALITY": self._functionality(),
             "STAKEHOLDER": f"{stakeholder['role'].replace('_', ' ')}",
             "STATEMENTS": block, "ISSUES": issue_lines, "N": str(n)},
            check, tag=f"followups.{stakeholder['id']}",
        )
        proposed: dict[str, dict[str, str]] = {}
        for f in items(payload, "followups"):
            sid = f.get("about_statement")
            if sid in ids and str(f.get("question", "")).strip() and sid not in proposed:
                proposed[sid] = {"about_statement": sid, "issue": str(f.get("issue", "vague")),
                                 "question": str(f.get("question", "")).strip()}

        # Rule-flagged answers come first and always get a follow-up — the model's
        # wording when it proposed one, a template question otherwise. Then any
        # further problems only the model noticed, up to two more.
        by_id = {s["id"]: s for s in statements}
        ordered: list[dict[str, str]] = []
        for i in issues:
            sid = i["statement_id"]
            ordered.append(proposed.pop(sid, None) or {
                "about_statement": sid, "issue": i["issue"],
                "question": self._template_followup(by_id[sid], i)})
        ordered.extend(list(proposed.values())[:2])
        return [{"id": f"FQ{k}", **f} for k, f in enumerate(ordered, start=1)]

    @staticmethod
    def _template_followup(statement: dict[str, Any], issue: dict[str, str]) -> str:
        quote = statement["text"][:120]
        if issue["issue"] == "vague":
            return (f'You said: "{quote}". Could you make that specific — a number, a '
                    "limit, a time or a concrete rule we could test?")
        return f'You said: "{quote}". What exact number or threshold should apply?'
