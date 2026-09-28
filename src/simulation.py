"""Simulated stakeholders — part of the evaluation harness, not of the system.

Each persona answers interview and clarification questions only from its hidden
fact sheet in cases/<id>/case.yaml, played by the secondary model so that the
system (primary model) is never interviewing itself.

Seeded ambiguity: a fact with a `vague` wording is stated vaguely until the system
aims a follow-up or clarification question at a statement that carries it. The
coordinator then unlocks the fact and the persona gives the precise version. A
seeded ambiguity counts as detected exactly when it was unlocked this way.

Answers carry the ids of the facts they used. Those ids are stored on the statement
for scoring and stripped by the blackboard before any agent reads it.
"""

from __future__ import annotations

import re
from typing import Any

from . import load_pipeline
from .generate_reqs import load_prompt, render
from .llm import LLMError


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "must", "be", "i",
        "we", "it", "is", "my", "our", "with", "that", "this", "should", "will", "not"}


class SimulatedStakeholder:
    def __init__(self, persona: dict[str, Any], client: Any, model_key: str | None = None) -> None:
        self.persona = persona
        self.client = client
        self.model_key = model_key or load_pipeline()["agents"]["persona_model"]
        self.unlocked: set[str] = set()

    @property
    def id(self) -> str:
        return self.persona["id"]

    def fact_ids(self) -> set[str]:
        return {f["id"] for f in self.persona.get("facts", [])}

    def unlock(self, fact_ids: list[str]) -> None:
        self.unlocked |= set(fact_ids) & self.fact_ids()

    def facts_view(self) -> list[dict[str, str]]:
        view = []
        for f in self.persona.get("facts", []):
            precise = "vague" not in f or f["id"] in self.unlocked
            view.append({"id": f["id"], "text": f["text"] if precise else f["vague"]})
        return view

    def answer(self, questions: list[dict[str, str]], case_id: str) -> list[dict[str, Any]]:
        """-> [{question_id, answer, fact_ids}] for each question asked."""
        if not questions:
            return []
        facts = self.facts_view()
        prompt = render(
            load_prompt("agents/persona.txt"),
            NAME=self.persona.get("name", self.persona["id"]),
            ROLE=self.persona["role"].replace("_", " "),
            PERSONA=str(self.persona.get("persona", "")).strip(),
            STYLE=str(self.persona.get("style", "")).strip(),
            FACTS="\n".join(f"{f['id']}: {f['text']}" for f in facts),
            QUESTIONS="\n".join(f"{q['id']}: {q['question']}" for q in questions),
        )
        by_id: dict[str, dict[str, Any]] = {}
        try:
            resp = self.client.generate(
                self.model_key, prompt=prompt, json_mode=True, tag="persona.answer",
                meta={"case": case_id, "persona": self.id},
            )
            payload = resp.json()
            for a in payload.get("answers", []) if isinstance(payload, dict) else []:
                if isinstance(a, dict) and a.get("question_id"):
                    by_id[str(a["question_id"])] = a
        except (LLMError, ValueError):
            pass

        out = []
        known = self.fact_ids()
        for q in questions:
            a = by_id.get(q["id"], {})
            text = str(a.get("answer", "")).strip() or "I'm not sure — that isn't something I deal with."
            cited = [f for f in a.get("fact_ids", []) if f in known] if isinstance(a.get("fact_ids"), list) else []
            if not cited:
                cited = self._attribute(text, facts)
            out.append({"question_id": q["id"], "answer": text, "fact_ids": cited})
        return out

    def _attribute(self, answer: str, facts: list[dict[str, str]]) -> list[str]:
        """Fallback attribution when the persona did not name its facts: lexical overlap."""
        words = _tokens(answer)
        if len(words) < 4:
            return []
        best, best_score = None, 0.0
        for f in facts:
            fw = _tokens(f["text"])
            score = len(words & fw) / max(1, len(fw))
            if score > best_score:
                best, best_score = f["id"], score
        return [best] if best and best_score >= 0.34 else []
