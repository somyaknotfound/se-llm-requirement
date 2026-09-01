"""Ollama transport with exhaustive call logging.

Every call made anywhere in this project goes through `OllamaClient.generate` and
lands as one JSON line in `logs/llm_calls.jsonl` — model id, every sampling
parameter, the full prompt, the raw untouched response, token counts and
wall-clock latency. Failed attempts are logged too. That log is the evidence that
the reported results came from the parameters the report claims they came from;
without it the reproducibility section is an assertion rather than a record.

Smoke-test the transport before building on it:

    python -m src.llm --smoke
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from . import ensure_dir, load_models, load_pipeline, resolve


class LLMError(RuntimeError):
    """Transport or generation failure that survived all retries."""


class ModelUnavailableError(LLMError):
    """A configured model is not present in the local Ollama registry."""


@dataclass
class LLMResponse:
    call_id: str
    model_key: str
    model_id: str
    params: dict[str, Any]
    prompt: str
    system: str | None
    text: str
    latency_s: float
    prompt_tokens: int | None
    completion_tokens: int | None
    attempts: int
    created_at: str
    tag: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def json(self) -> Any:
        """Parse the response as JSON, tolerating fenced or prose-wrapped output.

        Small instruct models intermittently ignore `format=json` and wrap the
        object in ```json fences or a sentence of preamble. Recovering here rather
        than at each call site keeps that quirk in one place — but the raw text is
        what gets logged, so the recovery never hides what the model actually said.
        """
        return extract_json(self.text)


def extract_json(text: str) -> Any:
    """Best-effort JSON recovery from a model response.

    Raises ValueError if nothing parseable is present; callers escalate that to a
    repair prompt rather than guessing at the model's intent.
    """
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Strip a ```json ... ``` fence if present.
    if "```" in stripped:
        segments = stripped.split("```")
        for seg in segments:
            seg = seg.strip()
            if seg.lower().startswith("json"):
                seg = seg[4:].strip()
            if seg.startswith(("{", "[")):
                try:
                    return json.loads(seg)
                except json.JSONDecodeError:
                    continue

    # Fall back to the outermost balanced object or array in the text.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"no parseable JSON in response (first 300 chars): {stripped[:300]!r}")


class OllamaClient:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        log_path: Path | None = None,
    ) -> None:
        self.config = config or load_models()
        self.host = self.config["host"].rstrip("/")
        req = self.config.get("request", {})
        self.timeout_s = req.get("timeout_s", 600)
        self.max_retries = req.get("max_retries", 3)
        self.backoff_s = req.get("backoff_s", 4)

        if log_path is None:
            log_path = resolve(load_pipeline()["paths"]["logs"])
        self.log_path = log_path
        ensure_dir(self.log_path.parent)

    # -- registry ---------------------------------------------------------

    def available_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=15)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(
                f"cannot reach Ollama at {self.host} — is the daemon running? "
                f"Start it with `ollama serve`. ({exc})"
            ) from exc
        return [m["name"] for m in r.json().get("models", [])]

    def resolve_model(self, model_key: str) -> tuple[str, dict[str, Any]]:
        """Map a roster key ('primary') to a concrete model id and its params."""
        spec = self.config["models"].get(model_key)
        if spec is None:
            raise KeyError(f"unknown model key {model_key!r}; roster: {list(self.config['models'])}")
        spec = dict(spec)
        model_id = spec.pop("id")
        return model_id, spec

    def require(self, model_keys: list[str]) -> dict[str, str]:
        """Preflight: fail loudly and early if a roster model was never pulled.

        Deliberately does not auto-substitute a fallback. Silently swapping weights
        would make the report's model attribution false.
        """
        available = self.available_models()
        resolved: dict[str, str] = {}
        missing: list[tuple[str, str]] = []

        for key in model_keys:
            model_id, _ = self.resolve_model(key)
            match = _match_model(model_id, available)
            if match is None:
                missing.append((key, model_id))
            else:
                resolved[key] = match

        if missing:
            lines = [f"  - {key}: {mid}  ->  ollama pull {mid}" for key, mid in missing]
            raise ModelUnavailableError(
                "required models are not present in the local Ollama registry:\n"
                + "\n".join(lines)
                + f"\n\navailable locally: {available or '(none)'}\n"
                + "Declared fallbacks (edit config/models.yaml to use one): "
                + f"{self.config.get('fallbacks', [])}"
            )
        return resolved

    # -- generation -------------------------------------------------------

    def generate(
        self,
        model_key: str,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
        tag: str | None = None,
        meta: dict[str, Any] | None = None,
        **overrides: Any,
    ) -> LLMResponse:
        model_id, params = self.resolve_model(model_key)
        params.update(overrides)

        payload: dict[str, Any] = {
            "model": model_id,
            "prompt": prompt,
            "stream": False,
            "options": params,
            "keep_alive": "10m",  # avoid a reload between every trial in the 18-run matrix
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        call_id = uuid.uuid4().hex[:12]
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            started = time.perf_counter()
            created_at = datetime.now(timezone.utc).isoformat()
            try:
                r = requests.post(
                    f"{self.host}/api/generate", json=payload, timeout=self.timeout_s
                )
                r.raise_for_status()
                body = r.json()
                latency = time.perf_counter() - started

                response = LLMResponse(
                    call_id=call_id,
                    model_key=model_key,
                    model_id=model_id,
                    params=params,
                    prompt=prompt,
                    system=system,
                    text=body.get("response", ""),
                    latency_s=round(latency, 3),
                    prompt_tokens=body.get("prompt_eval_count"),
                    completion_tokens=body.get("eval_count"),
                    attempts=attempt,
                    created_at=created_at,
                    tag=tag,
                    meta=meta or {},
                )
                self._log({"event": "generate", "json_mode": json_mode, **asdict(response)})
                return response

            except requests.RequestException as exc:
                latency = time.perf_counter() - started
                last_exc = exc
                self._log(
                    {
                        "event": "generate_error",
                        "call_id": call_id,
                        "created_at": created_at,
                        "model_key": model_key,
                        "model_id": model_id,
                        "params": params,
                        "prompt": prompt,
                        "system": system,
                        "json_mode": json_mode,
                        "tag": tag,
                        "meta": meta or {},
                        "attempt": attempt,
                        "latency_s": round(latency, 3),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_s * attempt)

        raise LLMError(
            f"generation failed after {self.max_retries} attempts "
            f"(model={model_id}, tag={tag}): {last_exc}"
        ) from last_exc

    # -- logging ----------------------------------------------------------

    def _log(self, record: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _match_model(wanted: str, available: list[str]) -> str | None:
    """Match a roster id against `ollama list` output.

    Ollama appends ':latest' when a tag is omitted, and quantisation suffixes are
    common, so exact-match alone produces false negatives on correct setups.
    """
    if wanted in available:
        return wanted
    base = wanted.split(":")[0]
    for name in available:
        if name == f"{wanted}:latest" or name.startswith(f"{wanted}-"):
            return name
    for name in available:
        if name.split(":")[0] == base:
            return name
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Ollama transport smoke test")
    ap.add_argument("--smoke", action="store_true", help="run a live round-trip on both models")
    ap.add_argument("--list", action="store_true", help="list locally available models")
    args = ap.parse_args()

    client = OllamaClient()

    if args.list or not args.smoke:
        try:
            models = client.available_models()
        except LLMError as exc:
            print(f"FAIL: {exc}")
            return 1
        print(f"Ollama at {client.host} — {len(models)} model(s) available:")
        for m in models:
            print(f"  {m}")
        if not args.smoke:
            return 0

    try:
        resolved = client.require(["primary", "secondary"])
    except LLMError as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"roster resolved: {resolved}")

    ok = True
    for key in ("primary", "secondary"):
        try:
            resp = client.generate(
                key,
                prompt=(
                    'Reply with exactly this JSON object and nothing else: '
                    '{"status": "ok", "domain": "healthcare"}'
                ),
                json_mode=True,
                tag="smoke_test",
            )
            parsed = resp.json()
            print(
                f"  [{key}] {resp.model_id}  {resp.latency_s}s  "
                f"in={resp.prompt_tokens} out={resp.completion_tokens}  -> {parsed}"
            )
        except (LLMError, ValueError) as exc:
            print(f"  [{key}] FAIL: {exc}")
            ok = False

    print(f"\ncalls logged to {client.log_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
