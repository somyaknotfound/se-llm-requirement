"""Offline stand-ins for the model, the retriever and the embedder.

They let the whole multi-agent pipeline run without Ollama or the embedding model,
so the orchestration, permissions, persistence and artefact generation can be tested
on a laptop. The scripted model answers each agent's prompt with valid JSON built
from the ids it finds in the prompt; it tests plumbing, not language quality.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.index import Hit
from src.ingest import load_chunks

REQ_ID = re.compile(r"\b(?:FR|NFR)-[A-Z]+-\d{3}\b")


@dataclass
class FakeResponse:
    text: str
    call_id: str
    latency_s: float = 0.01

    def json(self) -> Any:
        return json.loads(self.text)


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def require(self, keys):
        return {k: k for k in keys}

    def model_digests(self):
        return {"fake-model:latest": "sha256:0000"}

    def resolve_model(self, key):
        return key, {"seed": 42}

    def generate(self, model_key, prompt, json_mode=False, tag=None, meta=None, **overrides):
        self.calls.append({"tag": tag, "model": model_key, "meta": meta, "prompt": prompt})
        payload = self.respond(tag or "", prompt)
        return FakeResponse(json.dumps(payload), uuid.uuid4().hex[:12])

    # -- scripted behaviour per agent task -------------------------------------------

    def respond(self, tag: str, prompt: str) -> Any:
        base = re.sub(r"\.repair$", "", tag)
        for prefix, handler in [
            ("stakeholder_interaction.questions", self.questions),
            ("stakeholder_interaction.followups", self.followups),
            ("persona.answer", self.persona),
            ("extraction.extract", self.extract),
            ("extraction.revise", self.revise),
            ("extraction.regenerate", self.revise),
            ("classification.classify", self.classify),
            ("conflict_detection.pairs", self.pairs),
            ("clarification.questions", self.clarify),
            ("compliance.map", self.compliance_map),
            ("compliance.gaps", self.compliance_gaps),
            ("security_privacy.stride", self.threats),
            ("risk_analysis.risk", self.risk),
            ("p3_critic", self.critic),
            ("sdlc_selection.factors", self.factors),
            ("sdlc_selection.explain", self.explain),
            ("sdlc_selection.tailor", self.tailor),
            ("documentation.stories", self.stories),
            ("documentation.use_cases", self.use_cases),
        ]:
            if base.startswith(prefix):
                return handler(prompt)
        return {}

    @staticmethod
    def _section(prompt: str, heading: str) -> str:
        m = re.search(rf"# {re.escape(heading)}\n(.*?)(?:\n# |\Z)", prompt, re.S)
        return m.group(1) if m else ""

    def questions(self, prompt):
        topics = [line.split("|")[0].strip() for line in self._section(prompt, "TOPICS TO COVER FOR THIS ROLE").splitlines()
                  if "|" in line and not line.startswith("Each line")]
        return {"questions": [{"topic": t, "question": f"Tell me about {t.replace('_', ' ')}?"} for t in topics[:4]]}

    def followups(self, prompt):
        ids = re.findall(r"^(S-[A-Z0-9]+-\d{2}) \|", prompt, re.M)
        return {"followups": [{"about_statement": i, "issue": "vague", "question": f"Could you be specific about {i}?"}
                              for i in ids[:2]]}

    def persona(self, prompt):
        facts = re.findall(r"^(F-[A-Z]+-\d{2}): (.+)$", prompt, re.M)
        qids = re.findall(r"^((?:Q|FQ|CQ)[\w-]*): ", self._section(prompt, "QUESTIONS"), re.M)
        answers = []
        for k, q in enumerate(qids):
            fid, text = facts[k % len(facts)] if facts else ("", "I don't know.")
            answers.append({"question_id": q, "answer": text, "fact_ids": [fid] if fid else []})
        return {"answers": answers}

    def extract(self, prompt):
        ids = re.findall(r"^((?:S-[A-Z0-9]+-\d{2})|(?:DOC-[A-Z]+#p\d+)): (.+)$", prompt, re.M)
        chunks = re.findall(r"\[chunk_id: ([^\]]+)\]", prompt)
        reqs = []
        for k, (sid, text) in enumerate(ids[:4]):
            words = " ".join(text.split()[:12]).rstrip(".")
            cites = [chunks[0]] if chunks and k == 0 else (["D09#Sfake#c99"] if k == 1 else [])
            reqs.append({"statement": f"The system shall support: {words}.", "type": "FR" if k % 2 == 0 else "NFR",
                         "actor": "system", "priority": "Must", "acceptance_criteria": f"Verified within {k + 2} seconds.",
                         "verification_method": "Test", "risk_class": "Safety-critical" if k == 0 else "Standard",
                         "volatility": "Low", "business_justification": "stated by the stakeholder",
                         "source_statement_ids": [sid], "source_chunk_ids": cites, "evidence_quote": "",
                         "derived": False, "assumptions": ["network available"], "dependencies": []})
        return {"requirements": reqs, "out_of_scope": ["controlled substances"]}

    def revise(self, prompt):
        cur = re.search(r"^(?:FR|NFR)-[A-Z]+-\d{3}: (.+)$", prompt, re.M)
        ans = re.findall(r"^(S-[A-Z0-9]+-\d{2}): ", prompt, re.M)
        return {"statement": (cur.group(1) if cur else "The system shall respond.").rstrip(".") + " within 2 seconds.",
                "acceptance_criteria": "Measured response within 2 seconds for 95% of requests.",
                "verification_method": "Test", "source_statement_ids": ans[:1], "resolved": ["ambiguity"], "unresolved": []}

    def classify(self, prompt):
        ids = re.findall(r"^(T-\d{3}) \|", prompt, re.M)
        return {"classifications": [{"req_id": i, "categories": ["functional", "security"] if k % 2 == 0 else ["performance"]}
                                    for k, i in enumerate(ids)]}

    def pairs(self, prompt):
        pids = re.findall(r"^(P\d+)$", prompt, re.M)
        rel = ["conflict", "duplicate"]
        return {"pairs": [{"pair_id": p, "relation": rel[k] if k < 2 else "overlap", "explanation": "scripted"}
                          for k, p in enumerate(pids)]}

    def clarify(self, prompt):
        ids = re.findall(r"^((?:FR|NFR)-[A-Z]+-\d{3}) \|", prompt, re.M)
        return {"questions": [{"req_id": i, "question": f"What exactly do you need for {i}?"} for i in ids]}

    def compliance_map(self, prompt):
        out, current = [], None
        for line in prompt.splitlines():
            m = re.match(r"^((?:FR|NFR)-[A-Z]+-\d{3}): ", line)
            if m:
                current, taken = m.group(1), False
                continue
            c = re.match(r"^\s+candidate (\S+) \|", line)
            if c and current:
                control = c.group(1)
                continue
            e = re.match(r"^\s+evidence \[([^\]]+)\]", line)
            if e and current and not taken:
                out.append({"req_id": current, "control_id": control, "relation": "satisfies",
                            "evidence_chunk_id": e.group(1), "rationale": "scripted"})
                taken = True
        return {"mappings": out}

    def compliance_gaps(self, prompt):
        ids = re.findall(r"^(\S+) \| .+ \| .+$", self._section(prompt, "UNCOVERED CONTROLS"), re.M)
        return {"proposals": [{"control_id": i, "statement": f"The system shall comply with {i}.",
                               "acceptance_criteria": "Inspection confirms it.", "verification_method": "Inspection"}
                              for i in ids]}

    def threats(self, prompt):
        ids = REQ_ID.findall(prompt)
        return {"threats": [
            {"stride": "Spoofing", "asset": "account", "description": "impersonation", "mitigated_by": ids[:1],
             "proposed_requirement": None},
            {"stride": "Information disclosure", "asset": "PHI", "description": "data leak", "mitigated_by": [],
             "proposed_requirement": {"statement": "The system shall encrypt health data at rest.",
                                      "acceptance_criteria": "Storage inspection shows AES-256."}},
            {"stride": "Repudiation", "asset": "audit", "description": "deny action", "mitigated_by": ids[1:2],
             "proposed_requirement": None}]}

    def risk(self, prompt):
        ids = re.findall(r"^((?:FR|NFR)-[A-Z]+-\d{3}) \[", prompt, re.M)
        return {"risks": [{"req_id": i, "category": "clinical_safety" if k == 0 else "technical",
                           "description": "scripted", "likelihood": 4 if k == 0 else 2, "impact": 5 if k == 0 else 2,
                           "mitigation": "test it"} for k, i in enumerate(ids)]}

    def critic(self, prompt):
        attrs = ["necessary", "unambiguous", "complete", "singular", "feasible", "verifiable", "conforming", "traceable"]
        return {"scores": {a: {"score": 1, "note": "ok"} for a in attrs}}

    def factors(self, prompt):
        names = re.findall(r"^([a-z_]+): 1 = ", prompt, re.M)
        ids = REQ_ID.findall(prompt)[:1]
        high = {"regulatory_criticality", "failure_consequence", "formal_verification_need",
                "documentation_rigour", "security_risk", "legacy_dependence", "schedule_budget_rigidity"}
        return {"factors": [{"factor": n, "score": 5 if n in high else 2, "justification": "scripted",
                             "cited_req_ids": ids} for n in names]}

    def explain(self, prompt):
        ids = sorted(set(REQ_ID.findall(prompt)))[:3]
        return {"explanation": "Scripted explanation.", "decisive_factors": ["regulatory_criticality"],
                "strongest_counterargument": "none", "cited_req_ids": ids}

    def tailor(self, prompt):
        names = [line.split("|")[0].strip() for line in self._section(prompt, "WORKFLOW PHASES").splitlines()
                 if "|" in line and not line.startswith("Each line")]
        return {"phases": [{"phase": n, "activities": [f"Tailored step for {n}"], "req_ids": []} for n in names[:3]]}

    def stories(self, prompt):
        ids = re.findall(r"^((?:FR|NFR)-[A-Z]+-\d{3}) \|", prompt, re.M)
        return {"stories": [{"req_id": i, "story": "As a prescriber, I want this, so that it works.",
                             "scenarios": ["Given a patient When I order Then it is checked"]} for i in ids]}

    def use_cases(self, prompt):
        ids = REQ_ID.findall(prompt)[:2]
        return {"use_cases": [{"id": "UC-1", "name": "Issue a prescription", "primary_actor": "prescriber",
                               "preconditions": ["signed in"], "main_flow": ["Open order", "Check alerts", "Sign"],
                               "alternate_flows": ["Alert blocks signing"], "postconditions": ["sent"],
                               "req_ids": ids}]}


class FakeRetriever:
    """Lexical search over the real chunks; same interface as index.Retriever."""

    def __init__(self) -> None:
        self._chunks = load_chunks()

    def search(self, query: str, k: int, allowed_docs=None):
        words = set(re.findall(r"[a-z]{4,}", query.lower()))
        scored = []
        for c in self._chunks:
            if allowed_docs and c["doc_id"] not in allowed_docs:
                continue
            overlap = len(words & set(re.findall(r"[a-z]{4,}", c["text"].lower())))
            scored.append((overlap, c))
        scored.sort(key=lambda x: -x[0])
        return [Hit(chunk_id=c["chunk_id"], doc_id=c["doc_id"], section=c["section"], heading=c["heading"],
                    text=c["text"], token_count=c["token_count"], score=float(s), rank=i + 1)
                for i, (s, c) in enumerate(scored[:k])]

    def section_chunks(self, doc_id, section):
        return [c for c in self._chunks if c["doc_id"] == doc_id and c["section"] == section]

    def chunk(self, chunk_id):
        return next((c for c in self._chunks if c["chunk_id"] == chunk_id), None)


def fake_embed(texts, dim: int = 256):
    """Deterministic hashed bag-of-words vectors, L2-normalised."""
    out = np.zeros((len(texts), dim), dtype="float32")
    for i, t in enumerate(texts):
        for w in re.findall(r"[a-z]{3,}", str(t).lower()):
            out[i, int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1.0
        n = np.linalg.norm(out[i])
        if n:
            out[i] /= n
    return out
