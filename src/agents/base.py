"""Shared machinery for the agents.

  * Blackboard — the shared state of one case run. Every agent reads and writes it
    through its declared permissions (config/pipeline.yaml -> agents.permissions);
    anything else raises PermissionDenied and is recorded as a security event. Fields
    the evaluation harness needs but agents must never see (the persona fact ids
    behind a statement) are stripped on every read.
  * AgentContext — what an agent is handed: the public part of the case, the
    blackboard, the LLM client, a retriever, and the decision log.
  * Agent.ask — the one way an agent calls the model: untrusted text is already
    spotlighted by the caller, the injection notice is prepended, the JSON is
    validated by the agent's own check, one repair attempt is made with the errors,
    the output is screened for PHI leaks, and the whole exchange is logged.

Agents degrade rather than abort: a call that still fails after its repair returns
its errors, and the caller records them and escalates the affected items.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .. import load_pipeline
from ..generate_reqs import load_prompt, render
from ..llm import LLMError
from ..security import UNTRUSTED_NOTICE, leak_check

# Harness-only fields. Present on the blackboard for scoring, never shown to agents.
HIDDEN_FIELDS = {"fact_ids"}

REPAIR_SUFFIX = """

# YOUR PREVIOUS RESPONSE
{PREVIOUS}

# PROBLEMS WITH IT
{ERRORS}

Return a corrected JSON object that fixes every problem above and follows the
OUTPUT FORMAT exactly. Return ONE JSON object and nothing else."""


class PermissionDenied(PermissionError):
    pass


def _strip_hidden(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_hidden(v) for k, v in value.items() if k not in HIDDEN_FIELDS}
    if isinstance(value, list):
        return [_strip_hidden(v) for v in value]
    return value


class Blackboard:
    """Shared case state with least-privilege access per agent."""

    def __init__(self, data: dict[str, Any] | None = None,
                 permissions: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = data if data is not None else {}
        self._perm = permissions if permissions is not None else load_pipeline()["agents"]["permissions"]

    def read(self, agent: str, key: str, default: Any = None) -> Any:
        if key not in self._perm.get(agent, {}).get("reads", []):
            self._deny(agent, "read", key)
        return _strip_hidden(copy.deepcopy(self._data.get(key, default)))

    def write(self, agent: str, key: str, value: Any) -> None:
        if key not in self._perm.get(agent, {}).get("writes", []):
            self._deny(agent, "write", key)
        self._data[key] = value

    def _deny(self, agent: str, action: str, key: str) -> None:
        self._data.setdefault("security_events", []).append(
            {"kind": "permission_denied", "agent": agent, "action": action, "key": key,
             "at": datetime.now(timezone.utc).isoformat()}
        )
        raise PermissionDenied(f"agent {agent!r} may not {action} {key!r}")

    # Privileged access, for the coordinator and the evaluation harness only.
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value

    def append(self, key: str, item: Any) -> None:
        self._data.setdefault(key, []).append(item)

    def to_dict(self) -> dict[str, Any]:
        return self._data


@dataclass
class AgentContext:
    case: dict[str, Any]              # public view: no persona facts
    board: Blackboard
    client: Any                       # OllamaClient, or a scripted client in tests
    run_dir: Path
    cfg: dict[str, Any] = field(default_factory=load_pipeline)
    retriever: Any = None             # index.Retriever, loaded lazily
    embedder: Any = None              # texts -> unit vectors; MiniLM unless a test injects one
    step: str = ""

    def embed(self, texts: list[str]):
        import numpy as np

        if self.embedder is None:
            from ..index import _embedder

            model = _embedder(self.cfg["retrieval"]["embedding_model"])
            self.embedder = lambda t: model.encode(t, normalize_embeddings=True)
        return np.asarray(self.embedder(list(texts)), dtype="float32")

    def log(self, agent: str, event: str, **fields: Any) -> None:
        record = {"at": datetime.now(timezone.utc).isoformat(), "case": self.case.get("id"),
                  "step": self.step, "agent": agent, "event": event, **fields}
        with (self.run_dir / "agent_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def security_event(self, **fields: Any) -> None:
        self.board.append("security_events", {"at": datetime.now(timezone.utc).isoformat(),
                                              "step": self.step, **fields})

    def get_retriever(self):
        if self.retriever is None:
            from ..index import load

            self.retriever = load()
        return self.retriever


class Agent:
    name = "agent"

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx
        self.model_key = ctx.cfg["agents"]["model"]

    # -- blackboard ---------------------------------------------------------

    def read(self, key: str, default: Any = None) -> Any:
        return self.ctx.board.read(self.name, key, default)

    def write(self, key: str, value: Any) -> None:
        self.ctx.board.write(self.name, key, value)

    # -- retrieval ------------------------------------------------------------

    def allowed_sources(self) -> set[str]:
        rule = self.ctx.cfg["agents"]["permissions"].get(self.name, {}).get("retrieval", [])
        case_sources = set(self.ctx.case.get("knowledge_sources", []))
        if rule == "case":
            return case_sources
        return set(rule) & case_sources

    def retrieve(self, query: str, k: int = 6):
        allowed = self.allowed_sources()
        if not allowed:
            self.ctx.security_event(kind="retrieval_denied", agent=self.name)
            raise PermissionDenied(f"agent {self.name!r} has no retrieval permission")
        return self.ctx.get_retriever().search(query, k, allowed)

    # -- the model --------------------------------------------------------------

    def ask(
        self,
        prompt_name: str,
        fields: dict[str, str],
        check: Callable[[Any], list[str]],
        tag: str,
        meta: dict[str, Any] | None = None,
        model_key: str | None = None,
        **overrides: Any,
    ) -> tuple[Any, list[str]]:
        prompt = UNTRUSTED_NOTICE + "\n\n" + render(load_prompt(f"agents/{prompt_name}.txt"), **fields)
        key = model_key or self.model_key
        meta = {"case": self.ctx.case.get("id"), "agent": self.name, **(meta or {})}
        call_ids: list[str] = []
        started = time.perf_counter()

        payload, errors, text = self._call(key, prompt, f"{self.name}.{tag}", meta, call_ids, check, overrides)
        if errors and text is not None:
            repair = prompt + REPAIR_SUFFIX.replace("{PREVIOUS}", text[:6000]).replace(
                "{ERRORS}", "\n".join(f"- {e}" for e in errors[:12]))
            payload, errors, text = self._call(key, repair, f"{self.name}.{tag}.repair", meta,
                                               call_ids, check, overrides)

        if text is not None:
            leaks = leak_check(text)
            if leaks:
                self.ctx.security_event(kind="phi_leak", agent=self.name, tag=tag, identifiers=leaks)

        self.ctx.log(self.name, tag, call_ids=call_ids, errors=errors[:12],
                     seconds=round(time.perf_counter() - started, 2))
        return payload, errors

    def _call(self, key, prompt, tag, meta, call_ids, check, overrides):
        try:
            resp = self.ctx.client.generate(key, prompt=prompt, json_mode=True, tag=tag,
                                            meta=meta, **overrides)
        except LLMError as exc:
            return None, [f"model call failed: {exc}"], None
        call_ids.append(resp.call_id)
        try:
            payload = resp.json()
        except ValueError as exc:
            return None, [f"response was not parseable JSON: {exc}"], resp.text
        try:
            errors = check(payload)
        except Exception as exc:  # a malformed payload can break a check; that is an error too
            errors = [f"response did not match the expected structure: {exc}"]
        return payload, errors, resp.text


# --- small helpers shared by several agents ---------------------------------


def items(payload: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    value = payload.get(key)
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def expect_list(payload: Any, key: str, minimum: int = 1) -> list[str]:
    if not isinstance(payload, dict):
        return ["top-level JSON must be an object"]
    value = payload.get(key)
    if not isinstance(value, list):
        return [f"'{key}' must be an array"]
    if len(value) < minimum:
        return [f"'{key}' must contain at least {minimum} item(s)"]
    return []


def as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [v.strip() for v in value.replace(",", ";").split(";") if v.strip()]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def requirement_table(reqs: list[dict[str, Any]], fields: tuple[str, ...] = ("type", "statement")) -> str:
    lines = []
    for r in reqs:
        extra = " | ".join(str(r.get(f, "")) for f in fields if f != "statement")
        lines.append(f"{r['req_id']} | {extra} | {r.get('statement', '')}" if extra
                     else f"{r['req_id']} | {r.get('statement', '')}")
    return "\n".join(lines)


def active(reqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in reqs if r.get("status", "active") == "active"]
