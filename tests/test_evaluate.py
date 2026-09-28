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
