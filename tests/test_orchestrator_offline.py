"""The whole multi-agent pipeline, offline, with the scripted model."""

import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from src import store
from src.agents import Blackboard, PermissionDenied
from src.orchestrator import STEPS, Coordinator
from src.security import QUARANTINE_NOTE

from .fakes import FakeLLM, FakeRetriever, fake_embed


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    run_dir = tmp_path_factory.mktemp("erx_issuance")
    llm = FakeLLM()
    coord = Coordinator("erx_issuance", client=llm, retriever=FakeRetriever(), embedder=fake_embed, run_dir=run_dir)
    manifest = coord.run()
    return coord, manifest, llm, run_dir


def board(run):
    return run[0].board.to_dict()


def test_every_step_completes(run):
    assert board(run)["completed_steps"] == STEPS


def test_documents_are_masked_and_the_injection_is_quarantined(run):
    b = board(run)
    kinds = {(e["kind"], e.get("source")) for e in b["security_events"]}
    assert ("prompt_injection", "DOC-EMAIL") in kinds
    assert ("phi_masked", "DOC-INCIDENT") in kinds
    docs = [s for s in b["statements"] if s["source_type"] == "document"]
    text = " ".join(s["text"] for s in docs)
    assert "Jane Holloway" not in text and "AB1234563" not in text
    assert "ignore all previous instructions" not in text.lower()
    assert QUARANTINE_NOTE in text


def test_persona_facts_never_reach_an_agent_prompt(run):
    _, _, llm, _ = run
    agent_prompts = [c["prompt"] for c in llm.calls if not str(c["tag"]).startswith("persona.")]
    assert agent_prompts
    assert not any(re.search(r"\bF-[A-Z]+-\d{2}\b", p) for p in agent_prompts)
    # Every agent prompt carries the injection notice; the critic's comes from validate.py.
    assert all("UNTRUSTED" in c["prompt"] for c in llm.calls
               if not str(c["tag"]).startswith(("persona.", "p3_critic")))


def test_personas_run_on_the_second_model(run):
    _, _, llm, _ = run
    persona_models = {c["model"] for c in llm.calls if c["tag"] == "persona.answer"}
    agent_models = {c["model"] for c in llm.calls if str(c["tag"]).startswith("extraction.")}
    assert persona_models == {"secondary"} and agent_models == {"primary"}


def test_requirements_have_ids_and_trace_to_statements(run):
    b = board(run)
    statement_ids = {s["id"] for s in b["statements"]}
    live = [r for r in b["requirements"] if r.get("status", "active") == "active"]
    assert live
    for r in live:
        assert re.fullmatch(r"(FR|NFR)-ERX-\d{3}", r["req_id"])
        assert r["categories"]
        if r["origin"] in {"stakeholder", "document"}:
            assert set(r["source_statement_ids"]) <= statement_ids
    assert any(r.get("invalid_chunk_ids") for r in b["requirements"])     # recorded, not dropped


def test_conflicts_duplicates_and_clarification(run):
    b = board(run)
    relations = {c["relation"] for c in b["conflicts"]}
    assert "conflict" in relations
    assert any(e["event"] == "clarified" for e in b["requirement_history"])
    assert b["clarifications"]
    assert any(s["source_type"] == "interview" and str(s["round"]).startswith("c") for s in b["statements"])


def test_seeded_vague_facts_can_be_unlocked(run):
    unlocked = set().union(*[set(v) for v in board(run)["unlocked"].values()])
    assert unlocked       # follow-ups and clarification unlocked facts behind targeted statements


def test_compliance_mappings_point_at_the_controls_own_section(run):
    from src.knowledge import controls_by_id

    catalogue = controls_by_id()
    for row in board(run)["compliance"]:
        control = catalogue[row["control_id"]]
        if row["evidence_chunk_id"]:
            doc, sec = row["evidence_chunk_id"].split("#")[:2]
            assert (doc, sec[1:]) == (control["doc"], control["section"])
        assert row["needs_officer_approval"]


def test_gap_and_threat_proposals_join_the_set(run):
    origins = {r.get("origin") for r in board(run)["requirements"]}
    assert "security_threat" in origins
    assert board(run)["gaps"]


def test_quality_is_measured_before_and_after_clarification(run):
    labels = [s["label"] for s in board(run)["validation"]["snapshots"]]
    assert labels[0] == "v1" and "final" in labels


def test_sdlc_recommendation_and_workflow(run):
    sdlc = board(run)["sdlc"]
    assert sdlc["status"] == "pending_approval"
    assert sdlc["recommendation"]["ranking"][0]["pct"] >= sdlc["recommendation"]["ranking"][-1]["pct"]
    assert sdlc["workflow"] and any(p["gate"] for p in sdlc["workflow"])


def test_artefacts_are_written(run):
    out = run[3] / "artifacts"
    for name in ["srs.md", "user_stories.md", "use_cases.md", "process_workflow.md", "rtm.csv",
                 "compliance_matrix.csv", "risk_register.csv", "threat_register.csv",
                 "assumptions_dependencies.csv", "open_issues.csv", "data_requirements.md",
                 "interface_requirements.md", "sdlc_recommendation.md"]:
        assert (out / name).exists(), name
    assert "## 2. Requirements" in (out / "srs.md").read_text(encoding="utf-8")


def test_manifest_records_models_and_knowledge_base(run):
    manifest = run[1]
    assert manifest["model_digests"] and manifest["knowledge_base"]["kb_version"]
    assert set(manifest["seconds_by_step"]) == set(STEPS)
    assert json.loads((run[3] / "run_manifest.json").read_text())["case"] == "erx_issuance"


def test_approvals_rbac_and_applying_decisions(run):
    coord, _, _, run_dir = run
    with sqlite3.connect(store.db_path(run_dir)) as con:
        n = con.execute("SELECT COUNT(*) FROM approvals").fetchone()[0]
    assert n == len(board(run)["approvals"]) and n > 0

    items = store.approvals(run_dir)
    base = items[items["item_type"] == "requirement_baseline"]
    first, second = base.iloc[0], base.iloc[1]
    with pytest.raises(PermissionError):
        store.decide(run_dir, first["id"], "accept", "eve", "architect")
    with pytest.raises(ValueError):
        store.decide(run_dir, second["id"], "modify", "sam", "product_owner")          # no text
    store.decide(run_dir, first["id"], "accept", "sam", "product_owner")
    store.decide(run_dir, second["id"], "modify", "sam", "product_owner",
                 modified_text="The system shall return the check result within 2 seconds.")
    with pytest.raises(ValueError):
        store.decide(run_dir, first["id"], "reject", "sam", "product_owner")         # already decided

    counts = coord.apply_decisions()
    assert counts["accepted"] == 1 and counts["modified"] == 1
    reqs = {r["req_id"]: r for r in coord.board.get("requirements")}
    assert reqs[first["item_id"]]["approval_status"] == "approved"
    assert reqs[second["item_id"]]["statement"].endswith("within 2 seconds.")
    assert len(store.decisions(run_dir)) == 2                                          # log kept


def test_resume_makes_no_new_model_calls(run):
    _, _, _, run_dir = run
    llm = FakeLLM()
    again = Coordinator("erx_issuance", client=llm, retriever=FakeRetriever(), embedder=fake_embed, run_dir=run_dir)
    again.run(resume=True)
    assert llm.calls == []


PROMPT_DIGEST = """
import hashlib, tempfile
from pathlib import Path
from src.orchestrator import Coordinator
from tests.fakes import FakeLLM, FakeRetriever, fake_embed
llm = FakeLLM()
with tempfile.TemporaryDirectory() as d:
    Coordinator("erx_issuance", client=llm, retriever=FakeRetriever(), embedder=fake_embed, run_dir=Path(d)).run()
print(hashlib.sha256(repr([(c["tag"], c["model"], c["prompt"]) for c in llm.calls]).encode()).hexdigest())
"""


def test_prompts_are_identical_across_processes():
    """With fixed seeds, a model run is reproducible only if every prompt is byte-identical.
    Set iteration order changes with PYTHONHASHSEED, so compare two processes."""
    root = Path(__file__).resolve().parent.parent
    digests = {
        subprocess.run([sys.executable, "-c", PROMPT_DIGEST], cwd=root, env={**os.environ, "PYTHONHASHSEED": seed},
                       capture_output=True, text=True, check=True).stdout.split()[-1]
        for seed in ("1", "2")
    }
    assert len(digests) == 1


def test_blackboard_enforces_least_privilege():
    bb = Blackboard({"statements": [{"id": "S-1", "text": "x", "fact_ids": ["F-X-01"]}]})
    seen = bb.read("stakeholder_interaction", "statements")
    assert "fact_ids" not in seen[0]
    with pytest.raises(PermissionDenied):
        bb.write("classification", "approvals", [])
    with pytest.raises(PermissionDenied):
        bb.read("risk_analysis", "statements")
    assert [e["kind"] for e in bb.get("security_events")] == ["permission_denied", "permission_denied"]
