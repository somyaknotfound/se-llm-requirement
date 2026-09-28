import re

import pandas as pd

from src import load_pipeline, resolve
from src.cases import case_ids, load_case, load_gold
from src.ingest import load_chunks
from src.knowledge import controls_by_id, load_controls, load_stakeholder_templates
from src.sdlc_engine import evaluate, factor_names, load_sdlc

CASES = case_ids()


def test_three_case_studies_exist():
    assert set(CASES) == {"erx_issuance", "epcs_signing", "refill_reminders"}


def test_every_control_resolves_to_a_corpus_section():
    sections = {(c["doc_id"], c["section"]) for c in load_chunks()}
    for control in load_controls():
        assert (control["doc"], control["section"]) in sections, control["id"]
        assert set(control["applies_to"]) <= set(CASES), control["id"]


def test_manifest_carries_knowledge_base_metadata():
    man = pd.read_csv(resolve(load_pipeline()["paths"]["manifest"]))
    for col in ["jurisdiction", "authority", "effective_date", "version", "applicability"]:
        assert man[col].notna().all(), col


def test_cases_are_internally_consistent():
    roles = load_stakeholder_templates()["roles"]
    doc_ids = {f"D0{i}" for i in range(1, 7)}
    for cid in CASES:
        case = load_case(cid)
        assert set(case["knowledge_sources"]) <= doc_ids
        for p in case["stakeholders"]:
            assert p["role"] in roles, (cid, p["id"])
            for f in p["facts"]:
                assert f["id"].startswith(f"F-{p['id']}-"), f["id"]
        for d in case["documents"]:
            assert d["text"].strip(), d["id"]


def test_gold_standards_reference_real_facts_documents_and_controls():
    controls = controls_by_id()
    for cid in CASES:
        case, gold = load_case(cid), load_gold(cid)
        facts = {f["id"]: (p["id"], f) for p in case["stakeholders"] for f in p["facts"]}
        docs = {d["id"] for d in case["documents"]}
        for g in gold["requirements"]:
            assert "shall" in g["statement"], g["id"]
            for s in g["sources"]:
                assert s in facts or s in docs or s.startswith("control:"), (g["id"], s)
            for c in g.get("controls", []):
                assert c in controls, (g["id"], c)
            assert set(g["categories"]) <= set(load_pipeline()["categories"]), g["id"]
        for fid in gold["seeded_ambiguities"]:
            assert "vague" in facts[fid][1], fid
        for conflict in gold["seeded_conflicts"]:
            a, b = conflict["facts"]
            assert facts[a][0] != facts[b][0], conflict["id"]   # two different stakeholders
        for inj in gold["injections"]:
            assert inj["document"] in docs
            for p in inj["success_patterns"]:
                re.compile(p)
        assert gold["expert_sdlc"]["top"] == "", "expert SDLC is a human judgement; code never fills it"


def test_sdlc_config_is_well_formed():
    cfg = load_sdlc()
    names = set(factor_names())
    assert len(names) == 13
    for model, profile in cfg["profiles"].items():
        assert set(profile) <= names, model
        assert all(int(s["dir"]) in (-1, 1) and s["source"] for s in profile.values()), model
        assert model in cfg["workflows"], model
    scores = {f: 3 for f in names}
    for rule in cfg["rules"]:
        evaluate(rule["when"], scores)            # parses
        assert rule["model"] in cfg["profiles"]
