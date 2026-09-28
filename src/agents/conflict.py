"""Conflict-detection agent: duplicates and contradictions (brief point 10).

Candidate pairs come from rules, the judgement from the model:

  * Embedding similarity finds requirements about the same subject. A pair at or
    above the duplicate threshold is a duplicate candidate; a pair above the
    same-subject threshold is a conflict candidate when a rule signal fires or the
    two come from different stakeholders.
  * Rule signals: the same unit with different numbers ("within 2 seconds" vs
    "within 5 seconds"), negation on one side only ("shall allow" vs "shall not"),
    automation against human review.
  * The model labels each candidate pair duplicate, conflict, overlap or
    independent, a handful of pairs per call.

Confirmed duplicates are merged: the requirement with more sources survives and
absorbs the other's links. Conflicts are never resolved here — both requirements
get a finding, and the conflict goes to clarification and then to the product owner.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Agent, active, items

_NUM_UNIT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(%|percent|ms|milliseconds?|seconds?|minutes?|mins?|hours?|days?|"
    r"weeks?|months?|years?|ml|millilitres?|requests?)\b", re.I)
_NEGATION = re.compile(r"\b(shall not|must not|never|prohibit\w*|prevent\w*|without|no longer|block\w*)\b", re.I)
_AUTOMATION = re.compile(r"\b(automatic\w*|auto-\w+|one[- ]click|single click|without (typing|asking|review))\b", re.I)
_REVIEW = re.compile(r"\b(review\w*|confirm\w*|approv\w*|reason|acknowledg\w*|justif\w*)\b", re.I)

UNIT_ALIASES = {"percent": "%", "milliseconds": "ms", "millisecond": "ms", "second": "s", "seconds": "s",
                "minute": "min", "minutes": "min", "mins": "min", "hour": "h", "hours": "h",
                "day": "d", "days": "d", "week": "w", "weeks": "w", "month": "mo", "months": "mo",
                "year": "y", "years": "y", "millilitre": "ml", "millilitres": "ml", "request": "req",
                "requests": "req"}


def _quantities(text: str) -> dict[str, set[float]]:
    out: dict[str, set[float]] = {}
    for value, unit in _NUM_UNIT.findall(text):
        u = UNIT_ALIASES.get(unit.lower(), unit.lower())
        out.setdefault(u, set()).add(float(value))
    return out


def rule_signals(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    ta = f"{a['statement']} {a.get('acceptance_criteria', '')}"
    tb = f"{b['statement']} {b.get('acceptance_criteria', '')}"
    signals = []
    qa, qb = _quantities(ta), _quantities(tb)
    for unit in qa.keys() & qb.keys():
        if qa[unit] != qb[unit]:
            signals.append(f"different values in {unit}: {sorted(qa[unit])} vs {sorted(qb[unit])}")
    if bool(_NEGATION.search(a["statement"])) != bool(_NEGATION.search(b["statement"])):
        signals.append("negation on one side only")
    if (_AUTOMATION.search(ta) and _REVIEW.search(tb)) or (_AUTOMATION.search(tb) and _REVIEW.search(ta)):
        signals.append("automation against human review or justification")
    return signals


def _stakeholders(req: dict[str, Any]) -> set[str]:
    return {s.split("-")[1] for s in req.get("source_statement_ids", []) if s.startswith("S-") and s.count("-") >= 2}


class ConflictDetectionAgent(Agent):
    name = "conflict_detection"

    def candidates(self, reqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cfg = self.ctx.cfg["agents"]
        if len(reqs) < 2:
            return []
        vecs = self.ctx.embed([r["statement"] for r in reqs])
        sims = vecs @ vecs.T
        pairs = []
        for i in range(len(reqs)):
            for j in range(i + 1, len(reqs)):
                sim = float(sims[i, j])
                if sim < cfg["conflict_similarity"]:
                    continue
                a, b = reqs[i], reqs[j]
                signals = rule_signals(a, b)
                cross = bool(_stakeholders(a) and _stakeholders(b) and not (_stakeholders(a) & _stakeholders(b)))
                duplicate = sim >= cfg["duplicate_similarity"]
                if duplicate or signals or cross:
                    pairs.append({"a": a["req_id"], "b": b["req_id"], "similarity": round(sim, 3),
                                  "signals": signals, "duplicate_candidate": duplicate})
        # Rule-signalled pairs first, then by similarity; the cap bounds model calls.
        pairs.sort(key=lambda p: (not p["signals"], not p["duplicate_candidate"], -p["similarity"]))
        return pairs[: cfg["max_conflict_pairs"]]

    def judge(self, pairs: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        judged = []
        for start in range(0, len(pairs), 6):
            batch = pairs[start:start + 6]
            lines, index = [], {}
            for k, p in enumerate(batch, start=1):
                pid = f"P{k}"
                index[pid] = p
                hint = f"  hints: {'; '.join(p['signals'])}" if p["signals"] else ""
                lines.append(f"{pid}\n  A {p['a']}: {by_id[p['a']]['statement']}\n"
                             f"  B {p['b']}: {by_id[p['b']]['statement']}{hint}")

            def check(pl: Any, index=index) -> list[str]:
                got = {x.get("pair_id") for x in items(pl, "pairs")}
                errs = [f"no entry for {pid}" for pid in index if pid not in got]
                for x in items(pl, "pairs"):
                    if x.get("relation") not in {"duplicate", "conflict", "overlap", "independent"}:
                        errs.append(f"{x.get('pair_id')}: relation must be duplicate, conflict, overlap or independent")
                return errs

            payload, _ = self.ask("pair_relations", {"PAIRS": "\n".join(lines)}, check,
                                  tag=f"pairs.{start // 6 + 1}")
            answers = {x.get("pair_id"): x for x in items(payload, "pairs")}
            for pid, p in index.items():
                x = answers.get(pid, {})
                relation = x.get("relation")
                if relation not in {"duplicate", "conflict", "overlap", "independent"}:
                    relation = "unjudged"
                judged.append({**p, "relation": relation, "explanation": str(x.get("explanation", ""))})
        return judged

    def run(self) -> dict[str, int]:
        reqs = self.read("requirements", [])
        live = active(reqs)
        by_id = {r["req_id"]: r for r in reqs}
        judged = self.judge(self.candidates(live), by_id)

        history = self.read("requirement_history", [])
        conflicts = self.read("conflicts", [])
        findings = self.read("findings", [])
        merged = 0
        for p in judged:
            a, b = by_id[p["a"]], by_id[p["b"]]
            if a.get("status", "active") != "active" or b.get("status", "active") != "active":
                continue
            if p["relation"] == "duplicate":
                keep, drop = (a, b) if len(a["source_statement_ids"]) >= len(b["source_statement_ids"]) else (b, a)
                for field in ("source_statement_ids", "source_chunk_ids", "invalid_chunk_ids"):
                    keep[field] = list(dict.fromkeys(keep.get(field, []) + drop.get(field, [])))
                drop["status"] = "merged"
                drop["merged_into"] = keep["req_id"]
                history.append({"req_id": drop["req_id"], "event": "merged", "into": keep["req_id"],
                                "reason": p["explanation"]})
                merged += 1
            if p["relation"] in {"duplicate", "conflict"}:
                cid = f"CF-{len(conflicts) + 1:02d}"
                conflicts.append({"id": cid, "req_a": p["a"], "req_b": p["b"], "relation": p["relation"],
                                  "similarity": p["similarity"], "signals": p["signals"],
                                  "explanation": p["explanation"],
                                  "status": "merged" if p["relation"] == "duplicate" else "open"})
                if p["relation"] == "conflict":
                    for mine, other in ((a, b), (b, a)):
                        findings.append({"req_id": mine["req_id"], "kind": "conflict", "source": "llm",
                                         "detail": f"conflicts with {other['req_id']} ({cid}): {p['explanation']}",
                                         "round": 0, "resolved": False, "conflict_id": cid})

        self.write("requirements", reqs)
        self.write("requirement_history", history)
        self.write("conflicts", conflicts)
        self.write("findings", findings)
        self.ctx.log(self.name, "summary", pairs=len(judged), merged=merged,
                     conflicts=sum(1 for c in conflicts if c["relation"] == "conflict"))
        return {"pairs_judged": len(judged), "merged": merged,
                "conflicts": sum(1 for c in conflicts if c["relation"] == "conflict")}
