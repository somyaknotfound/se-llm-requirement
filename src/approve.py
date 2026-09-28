"""Human approval from the command line (brief points 16 and 17).

    python -m src.approve add-user --user laura --role compliance_officer --role privacy_officer
    python -m src.approve list   --case erx_issuance --user laura
    python -m src.approve decide --case erx_issuance --user laura APR-014 accept --note "mapping confirmed"
    python -m src.approve decide --case erx_issuance --user samuel APR-002 modify --text "The system shall ..."

Access control: every reviewer is a named user with one or more roles in
config/users.local.yaml (never committed). Signing in takes the password (PBKDF2,
never stored in clear) and a six-digit TOTP code from an authenticator app — two
factors. A reviewer can only see and decide items routed to one of their roles.

Non-interactive use (a notebook cell): set SE_APPROVER_PASSWORD and pass --otp.
The web UI (src/app.py) offers the same actions.
"""

from __future__ import annotations

import argparse
import getpass
import os
from typing import Any

import yaml

from . import resolve
from . import store
from .cases import case_out_dir
from .security import hash_password, new_totp_secret, verify_password, verify_totp

USERS_PATH = resolve("config") / "users.local.yaml"


def load_users() -> dict[str, Any]:
    if not USERS_PATH.exists():
        return {}
    return yaml.safe_load(USERS_PATH.read_text(encoding="utf-8")) or {}


def save_users(users: dict[str, Any]) -> None:
    USERS_PATH.write_text(yaml.safe_dump(users, sort_keys=True), encoding="utf-8")


def add_user(user: str, roles: list[str], password: str) -> str:
    users = load_users()
    secret = new_totp_secret()
    users[user] = {"roles": sorted(set(roles)), "password": hash_password(password), "totp": secret}
    save_users(users)
    return secret


def authenticate(user: str, password: str, otp: str) -> list[str]:
    """-> the user's roles, or PermissionError. Both factors are always checked."""
    record = load_users().get(user)
    ok = record is not None and verify_password(password, record["password"]) and verify_totp(record["totp"], otp)
    if not ok:
        raise PermissionError("sign-in failed: unknown user, wrong password or wrong one-time code")
    return list(record["roles"])


def _sign_in(args) -> list[str]:
    password = os.environ.get("SE_APPROVER_PASSWORD") or getpass.getpass(f"password for {args.user}: ")
    otp = args.otp or input("one-time code: ")
    return authenticate(args.user, password, otp)


def main() -> int:
    ap = argparse.ArgumentParser(description="Record human approval decisions")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add-user", help="create a reviewer with roles and a TOTP secret")
    a.add_argument("--user", required=True)
    a.add_argument("--role", action="append", required=True)

    ls = sub.add_parser("list", help="pending items for your roles")
    ls.add_argument("--case", required=True)
    ls.add_argument("--user", required=True)
    ls.add_argument("--otp")

    d = sub.add_parser("decide", help="accept, reject, modify or regenerate one item")
    d.add_argument("--case", required=True)
    d.add_argument("--user", required=True)
    d.add_argument("--otp")
    d.add_argument("--role", help="the role you act in, if you hold several")
    d.add_argument("approval_id")
    d.add_argument("decision", choices=sorted(store.DECISIONS))
    d.add_argument("--note", default="")
    d.add_argument("--text", default="", help="the modified requirement text, for a modify decision")

    b = sub.add_parser("decide-all", help="accept or reject every routine (normal-priority) item for a role")
    b.add_argument("--case", required=True)
    b.add_argument("--user", required=True)
    b.add_argument("--otp")
    b.add_argument("--role", help="the role you act in, if you hold several")
    b.add_argument("decision", choices=["accept", "reject"])
    b.add_argument("--note", required=True, help="what you reviewed before deciding")

    args = ap.parse_args()

    if args.cmd == "add-user":
        password = os.environ.get("SE_APPROVER_PASSWORD") or getpass.getpass("new password: ")
        if len(password) < 10:
            raise SystemExit("use a password of at least 10 characters")
        secret = add_user(args.user, args.role, password)
        print(f"created {args.user} with roles {sorted(set(args.role))}")
        print("add this secret to an authenticator app (TOTP, SHA-1, 6 digits, 30 s):")
        print(f"  {secret}")
        print(f"  otpauth://totp/SE-LLM-RE:{args.user}?secret={secret}&issuer=SE-LLM-RE")
        return 0

    roles = _sign_in(args)
    run_dir = case_out_dir(args.case)

    if args.cmd == "list":
        frame = store.approvals(run_dir)
        frame = frame[frame["required_role"].isin(roles)]
        if frame.empty:
            print(f"nothing pending for {args.user} ({', '.join(roles)})")
            return 0
        for _, r in frame.iterrows():
            flag = "!" if r["priority"] == "high" else " "
            print(f"{flag} {r['id']}  {r['required_role']:<24} {r['item_type']:<26} {r['item_id']:<14} {r['reason'][:80]}")
        return 0

    role = args.role or (roles[0] if len(roles) == 1 else None)
    if role is None or role not in roles:
        raise SystemExit(f"pass --role with one of your roles: {roles}")
    if args.cmd == "decide-all":
        done = store.decide_many(run_dir, args.decision, args.user, role, args.note)
        print(f"recorded {args.decision} on {len(done)} routine item(s) as {role}; "
              "high-priority items still need individual decisions")
        return 0
    rec = store.decide(run_dir, args.approval_id, args.decision, args.user, role, args.note, args.text)
    print(f"recorded: {rec['approval_id']} {rec['decision']} by {rec['user']} as {rec['role']}")
    print("apply decisions with: python -m src.orchestrator --case "
          f"{args.case} --apply-decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
