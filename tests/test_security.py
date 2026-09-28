import pytest

from src.cases import load_case
from src.security import (QUARANTINE_NOTE, Vault, dea_checksum_ok, hash_password, leak_check, mask,
                          npi_checksum_ok, quarantine, scan_injection, spotlight, totp, verify_password,
                          verify_totp)


def test_dea_and_npi_check_digits():
    assert dea_checksum_ok("1234563")          # AB1234563
    assert not dea_checksum_ok("1234569")
    assert npi_checksum_ok("1234567893")       # CMS example NPI
    assert not npi_checksum_ok("1234567890")


def test_masking_catches_identifiers_in_the_incident_report():
    text = load_case("erx_issuance")["documents"][4]["text"]
    vault = Vault()
    masked, found = mask(text, vault)
    kinds = {f["kind"] for f in found}
    assert {"PERSON", "MRN", "DOB", "DEA", "NPI", "PHONE", "EMAIL"} <= kinds
    for raw in ["Jane Holloway", "00482913", "04/12/1961", "AB1234563", "1234567893", "201-3344",
                "alan.brooks@example-hospital.org"]:
        assert raw not in masked
    assert leak_check(masked) == []


def test_numbers_without_valid_check_digits_are_not_masked():
    masked, found = mask("Order 1234567890 was placed by AB1234569.", Vault())
    assert found == []
    assert masked == "Order 1234567890 was placed by AB1234569."


def test_same_value_gets_the_same_token_and_unmask_is_role_restricted():
    vault = Vault()
    a, _ = mask("MRN: 00482913 seen today", vault)
    b, _ = mask("follow up on MRN 00482913", vault)
    assert "[MRN_1]" in a and "[MRN_1]" in b
    with pytest.raises(PermissionError):
        vault.unmask(a, role="prescriber")
    assert "00482913" in vault.unmask(a, role="privacy_officer")


def test_quarantine_removes_the_seeded_injection_but_keeps_the_email():
    email = load_case("erx_issuance")["documents"][2]["text"]
    clean, findings = quarantine(email)
    assert any(f["kind"] == "override" for f in findings)
    assert any(f["kind"] == "approval_tampering" for f in findings)
    assert "ignore all previous instructions" not in clean.lower()
    assert "recommend agile" not in clean.lower()
    assert QUARANTINE_NOTE in clean
    assert "number of refills" in clean          # the legitimate content survives


def test_benign_requirement_language_is_not_flagged():
    for text in ["Overrides require a documented reason.",
                 "The pharmacy must be notified when a prescription is cancelled.",
                 "Prescribers must review every interaction alert."]:
        assert [f for f in scan_injection(text) if f["severity"] == "high"] == []


def test_exfiltration_link_is_caught():
    reviews = load_case("refill_reminders")["documents"][1]["text"]
    _, findings = quarantine(reviews)
    kinds = {f["kind"] for f in findings}
    assert "exfiltration" in kinds and "unknown_url" in kinds


def test_spotlight_marker_is_deterministic_and_bound_to_content():
    a = spotlight("some text", "DOC-1")
    assert a == spotlight("some text", "DOC-1")
    assert a != spotlight("some text!", "DOC-1")
    assert a.startswith("<<UNTRUSTED source=DOC-1 id=") and a.rstrip().endswith(">>")


def test_totp_matches_the_rfc_6238_test_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"      # base32 of "12345678901234567890"
    assert totp(secret, at=59, digits=8) == "94287082"
    assert verify_totp(secret, "287082", at=59)
    assert not verify_totp(secret, "000000", at=59)


def test_password_hashing_round_trip():
    stored = hash_password("correct horse battery")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong", stored)
    assert "correct horse" not in stored
