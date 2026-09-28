import pytest

from src import approve, store
from src.security import totp


def _queue():
    base = {"status": "pending", "decision": "", "decided_by": "", "decided_at": "", "note": "", "modified_text": ""}
    return [
        {**base, "id": "APR-001", "item_type": "requirement_baseline", "item_id": "FR-X-001",
         "required_role": "product_owner", "reason": "baseline", "priority": "normal"},
        {**base, "id": "APR-002", "item_type": "requirement_baseline", "item_id": "FR-X-002",
         "required_role": "product_owner", "reason": "low confidence", "priority": "high"},
        {**base, "id": "APR-003", "item_type": "regulatory_interpretation", "item_id": "FR-X-001",
         "required_role": "compliance_officer", "reason": "mapping", "priority": "normal"},
    ]


def test_two_factor_sign_in(tmp_path, monkeypatch):
    monkeypatch.setattr(approve, "USERS_PATH", tmp_path / "users.yaml")
    secret = approve.add_user("laura", ["compliance_officer"], "a long enough password")
    assert approve.authenticate("laura", "a long enough password", totp(secret)) == ["compliance_officer"]
    with pytest.raises(PermissionError):
        approve.authenticate("laura", "a long enough password", "000000")
    with pytest.raises(PermissionError):
        approve.authenticate("laura", "wrong password", totp(secret))
    assert "a long enough password" not in (tmp_path / "users.yaml").read_text()


def test_bulk_decisions_skip_escalated_items_and_respect_roles(tmp_path):
    store.save(tmp_path, {"approvals": _queue()})
    done = store.decide_many(tmp_path, "accept", "sam", "product_owner", "read the SRS section 2.1")
    assert [d["approval_id"] for d in done] == ["APR-001"]           # APR-002 is high priority
    with pytest.raises(ValueError):
        store.decide_many(tmp_path, "accept", "sam", "product_owner", "x", priority="high")
    with pytest.raises(ValueError):
        store.decide_many(tmp_path, "accept", "sam", "product_owner", "")
    left = store.approvals(tmp_path)
    assert set(left["id"]) == {"APR-002", "APR-003"}
    log = store.decisions(tmp_path)
    assert list(log["note"]) == ["[bulk] read the SRS section 2.1"]
