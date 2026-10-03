import pandas as pd

from src import validate
from src.ingest import load_chunks

CHUNK = load_chunks()[70]          # a real chunk: D04 164.312


def _frame(rows):
    base = {"type": "NFR", "actor": "system", "priority": "Must", "verification_method": "Test",
            "risk_class": "Safety-critical", "volatility": "Low", "derived": False, "source_chunk_ids": "",
            "invalid_chunk_ids": "", "source_statement_ids": "", "evidence_quote": "", "reasoning": ""}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_traceability_rule_reads_invalid_chunk_ids_and_stakeholder_sources():
    df = _frame([
        {"req_id": "R1", "statement": "The system shall log access.", "acceptance_criteria": "An entry is logged.",
         "invalid_chunk_ids": "D05#S170.315(c)#c14"},
        {"req_id": "R2", "statement": "The system shall log access.", "acceptance_criteria": "An entry is logged.",
         "source_statement_ids": "S-SEC-01"},
        {"req_id": "R3", "statement": "The system shall lock sessions.", "acceptance_criteria": "Locked after 15 minutes.",
         "source_chunk_ids": CHUNK["chunk_id"]},
    ])
    scores = validate.score_rules(df)
    trace = scores[scores["attribute"] == "traceable"].set_index("req_id")["rule_score"]
    assert trace["R1"] == 0 and trace["R2"] == 1 and trace["R3"] == 1


def test_hallucination_audit_counts_guessed_and_invented_chunk_ids():
    df = _frame([
        {"req_id": "R1", "statement": "The system shall x.", "acceptance_criteria": "y",
         "invalid_chunk_ids": f"{CHUNK['chunk_id']};D09#Snope#c01"},
        {"req_id": "R2", "statement": "The system shall comply with 45 CFR 164.999.", "acceptance_criteria": "y"},
        {"req_id": "R3", "statement": "The system shall comply with 45 CFR 164.312(b).", "acceptance_criteria": "y"},
    ])
    audit = validate.audit_hallucinations(df)
    r1 = audit[audit["req_id"] == "R1"]
    assert (r1["verdict"] == "fabricated").sum() == 2
    assert any("was guessed" in e for e in r1["evidence"])
    assert audit[audit["req_id"] == "R2"]["verdict"].tolist() == ["fabricated"]
    assert audit[audit["req_id"] == "R3"]["verdict"].tolist() == ["verified"]
    assert set(audit[audit["req_id"] == "R2"]["severity"]) == {"high"}      # safety-critical


def test_confidence_caps_and_escalation():
    quote = CHUNK["text"][:80]
    df = _frame([
        {"req_id": "GOOD", "statement": "The system shall record audit events.",
         "acceptance_criteria": "Each event is recorded within 1 second.", "source_chunk_ids": CHUNK["chunk_id"],
         "evidence_quote": quote},
        {"req_id": "FAKE", "statement": "The system shall record audit events quickly.",
         "acceptance_criteria": "Recorded.", "invalid_chunk_ids": "D09#Snope#c01"},
        {"req_id": "CONF", "statement": "The system shall record audit events for 7 years.",
         "acceptance_criteria": "Retained 7 years.", "source_statement_ids": "S-PRES-01;S-SEC-02"},
    ])
    merged = validate.merge_scores(validate.score_rules(df), None)
    audit = validate.audit_hallucinations(df)
    conf = validate.confidence_table(df, merged, audit, conflicted={"CONF"}).set_index("req_id")
    assert conf.loc["GOOD", "support"] == 1.0 and not conf.loc["GOOD", "escalate"]
    assert conf.loc["FAKE", "confidence"] <= 0.3 and conf.loc["FAKE", "escalate"]
    assert conf.loc["CONF", "confidence"] <= 0.5 and conf.loc["CONF", "escalate"]
    queue = validate.review_queue(conf.reset_index(), df)
    assert queue.iloc[0]["escalate"] and (queue["human_decision"] == "").all()


def test_quotes_match_on_words_not_spacing_or_quote_marks():
    fhir = next(c for c in load_chunks() if c["chunk_id"] == "D01#S11.1.3#c09")
    assert '" numberOfRepeatsAllowed "' in fhir["text"]        # the HTML conversion's spacing
    df = _frame([
        {"req_id": "SPACING", "statement": "The system shall x.", "acceptance_criteria": "y",
         "source_chunk_ids": fhir["chunk_id"],
         "evidence_quote": '"numberOfRepeatsAllowed" : "< unsignedInt >", // Number of refills authorized'},
        {"req_id": "WRAPPED", "statement": "The system shall x.", "acceptance_criteria": "y",
         "source_chunk_ids": CHUNK["chunk_id"], "evidence_quote": f'"{CHUNK["text"][:80]}"'},
        {"req_id": "PARAPHRASE", "statement": "The system shall x.", "acceptance_criteria": "y",
         "source_chunk_ids": fhir["chunk_id"],
         "evidence_quote": "Technology must be able to record the number of refills a prescriber authorized."},
    ])
    audit = validate.audit_hallucinations(df)
    verdict = audit[audit["entity_type"] == "evidence_quote"].set_index("req_id")["verdict"]
    assert verdict["SPACING"] == "verified" and verdict["WRAPPED"] == "verified"
    assert verdict["PARAPHRASE"] == "fabricated"


def test_empty_adjudication_cells_are_not_counted_as_human_verdicts(tmp_path):
    from src.metrics import validation_metrics

    pd.DataFrame({"req_id": ["R1", "R2"], "attribute": ["verifiable"] * 2, "rule_score": [1, 0],
                  "llm_score": [1, 1], "agreement": ["agree", "disagree"],
                  "human_adjudication": [None, None]}).to_csv(tmp_path / "validation_29148.csv", index=False)
    rows = {r["metric"]: r["value"] for r in validation_metrics(tmp_path)}
    assert rows["human_adjudicated"] == 0
