"""Replay mode: recorded responses only, and never the real outputs."""

import json

import pytest

from src import load_models, load_pipeline
from src.llm import LLMError, OllamaClient, make_client
from src.replay import ReplayClient


@pytest.fixture
def log(tmp_path):
    params = {k: v for k, v in load_models()["models"]["primary"].items() if k != "id"}
    row = {"event": "generate", "call_id": "c1", "model_key": "primary", "model_id": "m", "params": params,
           "prompt": "hello", "system": None, "text": "recorded", "latency_s": 1.0, "prompt_tokens": 1,
           "completion_tokens": 1, "attempts": 1, "created_at": "t", "tag": "x", "meta": {}}
    path = tmp_path / "log.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return path


def test_an_identical_call_returns_the_recorded_response(log):
    client = ReplayClient(log)
    assert client.generate("primary", prompt="hello").text == "recorded"
    assert client.hits == 1 and not client.misses


@pytest.mark.parametrize("call", [
    {"model_key": "primary", "prompt": "hello "},
    {"model_key": "secondary", "prompt": "hello"},
    {"model_key": "primary", "prompt": "hello", "system": "other"},
    {"model_key": "primary", "prompt": "hello", "seed": 999},
])
def test_any_difference_is_a_miss_never_an_invented_answer(log, call):
    client = ReplayClient(log)
    with pytest.raises(LLMError):
        client.generate(**call)
    assert len(client.misses) == 1


def test_the_switch_changes_the_client_and_the_output_folder(monkeypatch):
    assert load_pipeline()["paths"]["outputs"] == "outputs"
    assert isinstance(make_client(), OllamaClient)
    monkeypatch.setenv("SE_REPLAY", "1")
    assert load_pipeline()["paths"]["outputs"] == "demo_outputs"
    assert isinstance(make_client(), ReplayClient)
