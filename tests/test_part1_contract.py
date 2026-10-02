import json

import pandas as pd
import pytest

from src import generate_reqs, load_pipeline, resolve
from src.index import Hit
from src.ingest import load_chunks

from .fakes import FakeResponse


def _req(i: int, kind: str, cites: list[str], derived: bool = False) -> dict:
    return {
        "req_id": f"{kind}-{i:02d}", "type": kind, "nfr_category": "none" if kind == "FR" else "security",
        "statement": f"The system shall do thing {i}.", "actor": "system", "priority": "Must",
        "verification_method": "Test", "acceptance_criteria": f"Thing {i} happens within 2 seconds.",
        "risk_class": "Standard", "volatility": "Low", "source_chunk_ids": cites, "derived": derived,
        "reasoning": "because", "evidence_quote": "", "inference_type": "direct_extraction",
    }


def _payload(n_fr: int, n_nfr: int, cites: list[str], bad: dict | None = None) -> dict:
    reqs = [_req(i, "FR", cites) for i in range(1, n_fr + 1)]
    reqs += [_req(i, "NFR", cites) for i in range(1, n_nfr + 1)]
    if bad:
        reqs.append(bad)
    return {"requirements": reqs}


def test_citation_integrity_is_flagged_not_fatal():
    cfg = load_pipeline()
    valid = {"D04#S164.312#c07"}
    fabricated = _req(9, "NFR", ["D05#S170.315(c)#c14"])
    records, errors, flags = generate_reqs.validate_payload(_payload(9, 8, list(valid), fabricated), valid, cfg)
    assert errors == []
    assert any("not present in the supplied evidence" in f for f in flags)
    assert any("derived=false" in f for f in flags)
    rec = next(r for r in records if r["req_id"] == "NFR-09")
    assert rec["invalid_chunk_ids"] == "D05#S170.315(c)#c14"
    assert rec["source_chunk_ids"] == ""


def test_count_violation_is_a_contract_error():
    cfg = load_pipeline()
    _, errors, _ = generate_reqs.validate_payload(_payload(8, 8, ["x"]), {"x"}, cfg)
    assert any("contract requires between" in e for e in errors)


def test_repair_prompt_carries_the_evidence():
    template = (resolve("prompts") / "p1_repair.txt").read_text(encoding="utf-8")
    assert "{EVIDENCE}" in template and "{DIRECTIVE}" in template


class ScriptedPart1:
    """First call: 16 requirements (count violation). Repair: 18, one with a guessed chunk id."""

    def __init__(self, first: dict, repair: dict):
        self.responses = [first, repair]
        self.prompts = []

    def require(self, keys):
        return {}

    def generate(self, model_key, prompt, json_mode=False, tag=None, meta=None, **kw):
        self.prompts.append((tag, prompt, kw))
        return FakeResponse(json.dumps(self.responses.pop(0)), f"call{len(self.prompts)}")


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    chunks = load_chunks()[60:66]
    hits = [Hit(c["chunk_id"], c["doc_id"], c["section"], c["heading"], c["text"], c["token_count"], 1.0, i)
            for i, c in enumerate(chunks, 1)]
    monkeypatch.setattr(generate_reqs, "retrieve_evidence", lambda **kw: hits)
    monkeypatch.setattr(generate_reqs, "output_dir", lambda case_id: tmp_path)
    return tmp_path, [c["chunk_id"] for c in chunks]


def test_colab_failure_now_completes_and_records_the_guessed_citation(isolated, monkeypatch):
    out, shown = isolated
    first = _payload(8, 8, shown[:1])
    repair = _payload(9, 8, shown[:1], _req(9, "NFR", ["D05#S170.315(c)#c14"]))
    client = ScriptedPart1(first, repair)
    monkeypatch.setattr(generate_reqs, "OllamaClient", lambda: client)

    assert generate_reqs.generate() == 0
    repair_tag, repair_prompt, window = client.prompts[1]
    assert repair_tag == "p1_repair"
    assert shown[0] in repair_prompt                  # the evidence is in the repair prompt
    assert window["num_ctx"] >= 32768

    reqs = pd.read_csv(out / "requirements.csv").fillna("")
    assert len(reqs) == 18
    row = reqs[reqs["req_id"] == "NFR-09"].iloc[0]
    assert row["invalid_chunk_ids"] == "D05#S170.315(c)#c14"
    contract = json.loads((out / "part1_contract.json").read_text())
    assert contract["used"] == "repair" and contract["final_flags"]


def test_a_repair_that_breaks_the_contract_falls_back_to_the_first_response(isolated, monkeypatch):
    out, shown = isolated
    first = _payload(9, 9, shown[:1], _req(10, "NFR", ["made-up"]))   # usable, one flag
    broken = _payload(3, 3, shown[:1])                                   # repair drops to 6
    monkeypatch.setattr(generate_reqs, "OllamaClient", lambda: ScriptedPart1(first, broken))
    assert generate_reqs.generate() == 0
    contract = json.loads((out / "part1_contract.json").read_text())
    assert contract["used"] == "initial_after_failed_repair"
    assert len(pd.read_csv(out / "requirements.csv")) == 19


def test_a_contract_failure_keeps_the_closer_attempt_and_records_it(isolated, monkeypatch):
    # The first GPU run: 19 requirements with too few NFRs; the repair shrank the set to 12.
    out, shown = isolated
    first = _payload(16, 3, shown[:1])
    shrunk = _payload(9, 3, shown[:1])
    monkeypatch.setattr(generate_reqs, "OllamaClient", lambda: ScriptedPart1(first, shrunk))
    assert generate_reqs.generate() == 0
    contract = json.loads((out / "part1_contract.json").read_text())
    assert contract["used"] == "initial_after_failed_repair" and not contract["contract_passed"]
    assert any("NFRs" in e for e in contract["final_errors"])
    assert len(pd.read_csv(out / "requirements.csv")) == 19


def test_output_with_no_requirements_still_aborts(isolated, monkeypatch):
    out, _ = isolated
    monkeypatch.setattr(generate_reqs, "OllamaClient", lambda: ScriptedPart1("not an object", {"requirements": []}))
    with pytest.raises(SystemExit):
        generate_reqs.generate()
    assert not json.loads((out / "part1_contract.json").read_text())["contract_passed"]
    assert not (out / "requirements.csv").exists()
