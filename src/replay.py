"""Replay mode: run the real pipeline on the recorded Run 2 model responses, with no model.

    set SE_REPLAY=1                                    (PowerShell: $env:SE_REPLAY = "1")
    python -m src.replay reset --case erx_issuance     fresh sandbox, that case not yet run
    python -m src.orchestrator --case erx_issuance
    python -m src.app

With SE_REPLAY set, every command works on `demo_outputs/` instead of `outputs/`, so a
demonstration cannot overwrite the reported results or the recorded human decisions, and
every model call is answered from logs/llm_calls.jsonl. A call is replayed only when the
model, the system prompt, the whole prompt and the sampling parameters are identical to a
recorded call; anything else is a miss, which the agents handle like a failed model call.
No response is ever invented. Retrieval, rules, scoring, storage and approvals run for real.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from . import PROJECT_ROOT, REPLAY_OUTPUTS, load_models, load_pipeline, replaying, resolve
from .llm import LLMError, LLMResponse


def _key(model_key: str, system: str | None, prompt: str, params: dict[str, Any]) -> tuple[str, ...]:
    return model_key, system or "", prompt, json.dumps(params, sort_keys=True)


class ReplayClient:
    def __init__(self, log_path: Path | None = None) -> None:
        self.config = load_models()
        self.log_path = log_path or resolve(load_pipeline()["paths"]["logs"])
        # The model sometimes answered the same call differently, so repeats play back in order.
        self.recorded: dict[tuple[str, ...], deque] = defaultdict(deque)
        with self.log_path.open(encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("event") == "generate":
                    self.recorded[_key(r["model_key"], r["system"], r["prompt"], r["params"])].append(r)
        self.hits = 0
        self.misses: list[str] = []

    def generate(self, model_key: str, prompt: str, system: str | None = None, json_mode: bool = False,
                 tag: str | None = None, meta: dict[str, Any] | None = None, **overrides: Any) -> LLMResponse:
        params = {k: v for k, v in self.config["models"][model_key].items() if k != "id"}
        params.update(overrides)
        takes = self.recorded.get(_key(model_key, system, prompt, params))
        if not takes:
            self.misses.append(tag or "")
            raise LLMError(f"replay mode has no recorded response for this prompt (tag={tag})")
        r = takes.popleft() if len(takes) > 1 else takes[0]
        self.hits += 1
        return LLMResponse(**{name: r[name] for name in LLMResponse.__dataclass_fields__})

    def require(self, model_keys: list[str]) -> dict[str, str]:
        return {k: self.config["models"][k]["id"] for k in model_keys}

    def model_digests(self) -> dict[str, str]:
        return {}

    def server_version(self) -> str:
        return f"replay of {self.log_path.name}"

    def summary(self) -> str:
        return f"replayed {self.hits} recorded model calls, {len(self.misses)} without a recording"


def reset(case_id: str) -> Path:
    """Rebuild the sandbox from the real results, then clear one case so it can be run live."""
    sandbox = PROJECT_ROOT / REPLAY_OUTPUTS
    source = PROJECT_ROOT / "outputs" / "cases"
    if not (source / case_id).is_dir():
        raise SystemExit(f"unknown case {case_id!r}; available: {sorted(p.name for p in source.iterdir())}")
    if sandbox.exists():
        shutil.rmtree(sandbox)
    shutil.copytree(source, sandbox / "cases", ignore=shutil.ignore_patterns("vault.enc"))
    for path in (sandbox / "cases" / case_id).iterdir():
        if path.name == "baseline":
            continue
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    return sandbox


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare the replay sandbox")
    ap.add_argument("cmd", choices=["reset"])
    ap.add_argument("--case", default="erx_issuance", help="the case to clear so it can be run live")
    args = ap.parse_args()
    sandbox = reset(args.case)
    print(f"sandbox ready: {sandbox} ({args.case} cleared; other cases hold the Run 2 results)")
    if not replaying():
        print("SE_REPLAY is not set in this window: commands here would use the real outputs/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
