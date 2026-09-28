"""Relational store of record for a case run (brief point 18).

    outputs/cases/<id>/re.db   SQLite: requirements, statements, findings, conflicts,
                               compliance, gaps, threats, risks, clarifications,
                               approvals, and an append-only decisions table

The run's tables are written once by the coordinator. Only the approval tooling
changes anything afterwards, and every change it makes is appended to `decisions`
with the reviewer's identity and role — the audit trail of human oversight.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

TABLES = ["requirements", "statements", "findings", "conflicts", "compliance", "gaps",
          "threats", "risks", "clarifications"]
DECISIONS = {"accept": "accepted", "reject": "rejected", "modify": "modified", "regenerate": "regenerate_requested"}
HIDDEN = {"fact_ids"}


def db_path(run_dir: Path) -> Path:
    return run_dir / "re.db"


def _flatten(rows: list[dict[str, Any]]) -> pd.DataFrame:
    out = []
    for r in rows:
        flat = {}
        for k, v in r.items():
            if k in HIDDEN:
                continue
            if isinstance(v, list):
                flat[k] = ";".join(json.dumps(x) if isinstance(x, dict) else str(x) for x in v)
            elif isinstance(v, dict):
                flat[k] = json.dumps(v, default=str)
            else:
                flat[k] = v
        out.append(flat)
    return pd.DataFrame(out)


def save(run_dir: Path, board: dict[str, Any], fresh: bool = True) -> Path:
    """Write the run's tables. `fresh` starts a new decision log: a new run is a new
    baseline, and decisions about the previous one's queue no longer apply."""
    path = db_path(run_dir)
    with sqlite3.connect(path) as con:
        if fresh:
            con.execute("DROP TABLE IF EXISTS decisions")
        for table in TABLES:
            rows = board.get(table) or []
            frame = _flatten(rows) if rows else pd.DataFrame()
            if frame.empty:
                con.execute(f"DROP TABLE IF EXISTS {table}")
                continue
            frame.to_sql(table, con, if_exists="replace", index=False)
        con.execute("DROP TABLE IF EXISTS approvals")
        con.execute("""CREATE TABLE approvals (
            id TEXT PRIMARY KEY, item_type TEXT, item_id TEXT, required_role TEXT, reason TEXT,
            priority TEXT, status TEXT, decision TEXT, decided_by TEXT, decided_at TEXT,
            note TEXT, modified_text TEXT)""")
        con.executemany(
            "INSERT INTO approvals VALUES (:id,:item_type,:item_id,:required_role,:reason,:priority,"
            ":status,:decision,:decided_by,:decided_at,:note,:modified_text)",
            board.get("approvals") or [],
        )
        con.execute("""CREATE TABLE IF NOT EXISTS decisions (
            at TEXT, approval_id TEXT, item_type TEXT, item_id TEXT, decision TEXT,
            user TEXT, role TEXT, note TEXT, modified_text TEXT)""")
    return path


def approvals(run_dir: Path, role: str | None = None, status: str | None = "pending") -> pd.DataFrame:
    with sqlite3.connect(db_path(run_dir)) as con:
        frame = pd.read_sql("SELECT * FROM approvals", con)
    if role:
        frame = frame[frame["required_role"] == role]
    if status:
        frame = frame[frame["status"] == status]
    rank = frame["priority"].map({"high": 0}).fillna(1)
    return frame.assign(_rank=rank).sort_values(["_rank", "id"]).drop(columns="_rank")


def decide(run_dir: Path, approval_id: str, decision: str, user: str, role: str,
           note: str = "", modified_text: str = "") -> dict[str, Any]:
    """Record one human decision. Enforces the role and the decision's preconditions."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {sorted(DECISIONS)}")
    if decision == "modify" and not modified_text.strip():
        raise ValueError("a modify decision needs the modified text")
    if decision == "regenerate" and not note.strip():
        raise ValueError("a regenerate decision needs a note telling the system what to change")
    with sqlite3.connect(db_path(run_dir)) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            raise KeyError(f"no approval item {approval_id}")
        if row["required_role"] != role:
            raise PermissionError(f"{approval_id} needs the {row['required_role']} role; you acted as {role}")
        if row["status"] != "pending":
            raise ValueError(f"{approval_id} is already {row['status']}")
        at = datetime.now(timezone.utc).isoformat()
        con.execute(
            "UPDATE approvals SET status=?, decision=?, decided_by=?, decided_at=?, note=?, modified_text=? "
            "WHERE id=?", (DECISIONS[decision], decision, user, at, note, modified_text, approval_id))
        con.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?)",
                    (at, approval_id, row["item_type"], row["item_id"], decision, user, role, note, modified_text))
    record = {"at": at, "approval_id": approval_id, "item_type": row["item_type"], "item_id": row["item_id"],
              "decision": decision, "user": user, "role": role, "note": note, "modified_text": modified_text}
    with (run_dir / "decisions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def decide_many(run_dir: Path, decision: str, user: str, role: str, note: str,
                priority: str = "normal") -> list[dict[str, Any]]:
    """Record the same decision on every pending item of one priority for one role.

    For routine items only: it refuses high-priority items, which are the escalated
    ones a reviewer must read individually. Each item still gets its own entry in the
    decision log, under the reviewer's identity.
    """
    if priority == "high":
        raise ValueError("high-priority items are escalated and must be decided one by one")
    if decision not in {"accept", "reject"}:
        raise ValueError("bulk decisions can only accept or reject")
    if not note.strip():
        raise ValueError("a bulk decision needs a note saying what was reviewed")
    pending = approvals(run_dir, role=role)
    pending = pending[pending["priority"] == priority]
    return [decide(run_dir, aid, decision, user, role, f"[bulk] {note}") for aid in pending["id"]]


def decisions(run_dir: Path) -> pd.DataFrame:
    path = db_path(run_dir)
    if not path.exists():
        return pd.DataFrame()
    with sqlite3.connect(path) as con:
        try:
            return pd.read_sql("SELECT * FROM decisions", con)
        except Exception:
            return pd.DataFrame()
