from src.evaluate import ambiguity_detection, conflict_detection, match, prf

from .fakes import fake_embed


def test_matching_is_one_to_one_and_thresholded():
    generated = [{"req_id": "FR-1", "statement": "The system shall lock the session after 15 minutes of inactivity."},
                 {"req_id": "FR-2", "statement": "The system shall lock the session after 15 minutes idle."},
                 {"req_id": "FR-3", "statement": "The app shall show a pickup notification."}]
    gold = [{"id": "G-1", "statement": "The system shall lock a session after 15 minutes of inactivity."},
            {"id": "G-2", "statement": "The system shall retain audit logs for 6 years."}]
    m = match(generated, gold, threshold=0.6, embed=fake_embed)
    assert [(x["gold_id"], x["req_id"]) for x in m] == [("G-1", "FR-1")]


def test_prf():
    assert prf(3, 6, 4) == {"precision": 0.5, "recall": 0.75, "f1": 0.6}
    assert prf(0, 0, 4)["f1"] == 0.0


def test_ambiguity_detection_counts_unlocked_seeded_facts():
    state = {"unlocked": {"PRES": ["F-PRES-02"], "SEC": ["F-SEC-02", "F-SEC-01"]}}
    gold = {"seeded_ambiguities": ["F-PRES-02", "F-SEC-02", "F-ARCH-03"]}
    res = ambiguity_detection(state, gold)
    assert res["value"] == round(2 / 3, 3) and "F-ARCH-03" in res["detail"]


def test_conflict_detection_maps_flags_back_to_seeded_facts():
    state = {
        "statements": [{"id": "S-PRES-01", "fact_ids": ["F-PRES-03"]}, {"id": "S-CSO-01", "fact_ids": ["F-CSO-02"]},
                       {"id": "S-PO-01", "fact_ids": ["F-PO-01"]}],
        "requirements": [{"req_id": "A", "source_statement_ids": ["S-PRES-01"]},
                         {"req_id": "B", "source_statement_ids": ["S-CSO-01"]},
                         {"req_id": "C", "source_statement_ids": ["S-PO-01"]}],
        "conflicts": [{"id": "CF-01", "req_a": "A", "req_b": "B", "relation": "conflict"},
                      {"id": "CF-02", "req_a": "A", "req_b": "C", "relation": "conflict"}],
    }
    gold = {"seeded_conflicts": [{"id": "C-1", "facts": ["F-PRES-03", "F-CSO-02"]},
                                 {"id": "C-2", "facts": ["F-PO-04", "F-CSO-06"]}]}
    res = conflict_detection(state, gold)
    assert res["recall"] == 0.5 and res["precision"] == 0.5


def test_simulated_verdicts_are_reported_apart_from_human_ones(tmp_path):
    import pandas as pd

    from src.evaluate import _verified_tp, _write_sheet

    sheet = tmp_path / "matches.csv"
    auto = [{"gold_id": "G1", "gold_statement": "g", "req_id": "R1", "statement": "s1", "similarity": 0.9},
            {"gold_id": "G2", "gold_statement": "g", "req_id": "R2", "statement": "s2", "similarity": 0.8}]
    _write_sheet(sheet, auto)
    frame = pd.read_csv(sheet).fillna("")
    frame["simulated_verdict"] = ["yes", "no"]
    frame.to_csv(sheet, index=False)

    _write_sheet(sheet, auto)                                   # a re-run keeps the verdicts
    assert _verified_tp(sheet, "simulated_verdict") == 1
    assert _verified_tp(sheet) is None                          # no human verdict, so no human-verified score

    auto[0]["statement"] = "s1 modified"                        # changed text: the old verdict no longer applies
    _write_sheet(sheet, auto)
    assert list(pd.read_csv(sheet).fillna("")["simulated_verdict"]) == ["", "no"]


def test_correction_rate_counts_each_requirement_once_across_roles(tmp_path):
    from src import store
    from src.evaluate import _human_corrections

    base = {"status": "pending", "decision": "", "decided_by": "", "decided_at": "", "note": "", "modified_text": "",
            "reason": "r", "priority": "high"}
    store.save(tmp_path, {"approvals": [
        {**base, "id": "A1", "item_type": "requirement_baseline", "item_id": "FR-1", "required_role": "product_owner"},
        {**base, "id": "A2", "item_type": "clinical_safety", "item_id": "FR-1", "required_role": "clinical_safety_officer"},
        {**base, "id": "A3", "item_type": "requirement_baseline", "item_id": "NFR-2", "required_role": "product_owner"},
        {**base, "id": "A4", "item_type": "conflict", "item_id": "CF-01", "required_role": "product_owner"},
    ]})
    store.decide(tmp_path, "A1", "accept", "u", "product_owner", "ok")
    store.decide(tmp_path, "A2", "modify", "u", "clinical_safety_officer", "fix", "The system shall X.")
    store.decide(tmp_path, "A3", "accept", "u", "product_owner", "ok")
    store.decide(tmp_path, "A4", "reject", "u", "product_owner", "false conflict")   # not a requirement
    rows = []
    _human_corrections(lambda system, metric, value, detail="": rows.append((metric, value, detail)), tmp_path)
    assert rows[0][1] == 0.5 and rows[0][2].startswith("1/2")
