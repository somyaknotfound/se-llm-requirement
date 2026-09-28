"""Compliance agent (brief point 11).

For every requirement it proposes the controls from config/controls.yaml that the
requirement satisfies, each backed by an evidence chunk from the control's own
section of the regulation. It then finds the applicable controls no requirement
covers — compliance gaps — and proposes a requirement for each.

It makes no legal determination. Every mapping and every gap proposal carries
`needs_officer_approval` and is queued for the compliance officer.

Candidates are chosen by embedding similarity between the requirement and each
control's obligation, so the model only ever judges a short list, and it can only
cite chunks from the candidate control's section: a mapping can never point at text
the control does not come from.
"""

from __future__ import annotations

import re
from typing import Any

from ..knowledge import applicable_controls
from ..security import spotlight
from .base import Agent, active, items

RELATIONS = {"satisfies", "partially"}


def _excerpt(text: str, anchor: str, limit: int = 360) -> str:
    """The sentences of a chunk that best match a control's obligation."""
    words = set(re.findall(r"[a-z]{4,}", anchor.lower()))
    sentences = [s.strip() for s in re.split(r"(?<=[.;])\s+|\n+", text) if len(s.strip()) > 20]
    ranked = sorted(sentences, key=lambda s: -len(words & set(re.findall(r"[a-z]{4,}", s.lower()))))
    out = ""
    for s in ranked:
        if len(out) + len(s) > limit:
            break
        out += s + " "
    return (out or text[:limit]).strip()


class ComplianceAgent(Agent):
    name = "compliance"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        allowed = self.allowed_sources()
        self.controls = [c for c in applicable_controls(ctx.case) if c["doc"] in allowed]
        self._evidence: dict[str, list[dict[str, Any]]] = {}

    def _evidence_pool(self, control: dict[str, Any]) -> list[dict[str, Any]]:
        if control["id"] not in self._evidence:
            chunks = self.ctx.get_retriever().section_chunks(control["doc"], control["section"])
            self._evidence[control["id"]] = chunks
        return self._evidence[control["id"]]

    def _best_chunk(self, control: dict[str, Any], text: str) -> dict[str, Any] | None:
        pool = self._evidence_pool(control)
        if len(pool) <= 1:
            return pool[0] if pool else None
        vecs = self.ctx.embed([f"{c['heading']}\n{c['text']}" for c in pool] + [text])
        scores = vecs[:-1] @ vecs[-1]
        return pool[int(scores.argmax())]

    def map_requirements(self) -> dict[str, int]:
        reqs = self.read("requirements", [])
        live = active(reqs)
        if not live or not self.controls:
            return {"mappings": 0}
        ctrl_vecs = self.ctx.embed([f"{c['title']}. {c['obligation']}" for c in self.controls])
        req_vecs = self.ctx.embed([r["statement"] for r in live])
        sims = req_vecs @ ctrl_vecs.T
        floor = self.ctx.cfg["agents"].get("compliance_similarity", 0.3)

        candidates: dict[str, list[tuple[dict[str, Any], float, dict[str, Any]]]] = {}
        for i, r in enumerate(live):
            order = sims[i].argsort()[::-1][:3]
            for j in order:
                if sims[i, j] < floor:
                    continue
                chunk = self._best_chunk(self.controls[j], r["statement"])
                if chunk:
                    candidates.setdefault(r["req_id"], []).append((self.controls[j], float(sims[i, j]), chunk))

        rows = self.read("compliance", [])
        by_id = {r["req_id"]: r for r in reqs}
        batch_ids = [rid for rid in candidates]
        for start in range(0, len(batch_ids), 4):
            batch = batch_ids[start:start + 4]
            lines = []
            allowed_pairs: dict[tuple[str, str], str] = {}
            for rid in batch:
                lines.append(f"{rid}: {by_id[rid]['statement']}")
                for control, _, chunk in candidates[rid]:
                    allowed_pairs[(rid, control["id"])] = chunk["chunk_id"]
                    lines.append(f"  candidate {control['id']} | {control['citation']} | {control['obligation']}")
                    lines.append(f"    evidence [{chunk['chunk_id']}]: {_excerpt(chunk['text'], control['obligation'])}")

            def check(p: Any, allowed_pairs=allowed_pairs) -> list[str]:
                errs = []
                if not isinstance(p, dict) or not isinstance(p.get("mappings"), list):
                    return ["'mappings' must be an array"]
                for m in items(p, "mappings"):
                    key = (m.get("req_id"), m.get("control_id"))
                    if key not in allowed_pairs:
                        errs.append(f"{key} is not one of the candidate pairs")
                    elif m.get("evidence_chunk_id") != allowed_pairs[key]:
                        errs.append(f"{key}: evidence_chunk_id must be {allowed_pairs[key]}")
                    if m.get("relation") not in RELATIONS:
                        errs.append(f"{key}: relation must be satisfies or partially")
                return errs

            payload, _ = self.ask("compliance_map", {"ITEMS": spotlight("\n".join(lines), "requirements")},
                                  check, tag=f"map.{start // 4 + 1}")
            sim_of = {(rid, c["id"]): s for rid in batch for c, s, _ in candidates[rid]}
            for m in items(payload, "mappings"):
                key = (m.get("req_id"), m.get("control_id"))
                if key not in allowed_pairs or m.get("relation") not in RELATIONS:
                    continue
                control = next(c for c in self.controls if c["id"] == key[1])
                rows.append({
                    "req_id": key[0], "control_id": key[1], "citation": control["citation"],
                    "relation": m["relation"], "evidence_chunk_id": allowed_pairs[key],
                    "rationale": str(m.get("rationale", "")), "similarity": round(sim_of[key], 3),
                    "needs_officer_approval": True, "status": "proposed",
                })

        mapped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            mapped.setdefault(row["req_id"], []).append(row)
        findings = self.read("findings", [])
        for r in live:
            mine = mapped.get(r["req_id"], [])
            r["control_ids"] = sorted({m["control_id"] for m in mine})
            r["regulations"] = sorted({m["citation"] for m in mine})
            if not mine and set(r.get("categories", [])) & {"security", "privacy", "regulatory"}:
                findings.append({"req_id": r["req_id"], "kind": "missing_control", "source": "rule",
                                 "detail": "a security, privacy or regulatory requirement mapped to no control",
                                 "round": 0, "resolved": False})
        self.write("requirements", reqs)
        self.write("compliance", rows)
        self.write("findings", findings)
        return {"mappings": len(rows), "requirements_mapped": len(mapped)}

    def uncovered(self) -> list[dict[str, Any]]:
        covered = {row["control_id"] for row in self.read("compliance", [])}
        return [c for c in self.controls if c["id"] not in covered]

    def propose_gaps(self) -> list[dict[str, Any]]:
        """One proposed requirement per uncovered control, for the compliance officer."""
        fn = self.ctx.case["functionality"]
        gaps = self.uncovered()
        proposals: list[dict[str, Any]] = []
        for start in range(0, len(gaps), 6):
            batch = gaps[start:start + 6]
            ids = {c["id"] for c in batch}

            def check(p: Any, ids=ids) -> list[str]:
                errs = []
                got = {x.get("control_id") for x in items(p, "proposals")}
                errs += [f"no proposal for {c}" for c in sorted(ids - got)]
                for x in items(p, "proposals"):
                    if "shall" not in str(x.get("statement", "")).lower():
                        errs.append(f"{x.get('control_id')}: the statement has no 'shall'")
                return errs

            payload, _ = self.ask(
                "compliance_gap",
                {"FUNCTIONALITY": f"{fn['name']}\n{fn['description'].strip()}",
                 "CONTROLS": "\n".join(f"{c['id']} | {c['citation']} | {c['obligation']}" for c in batch)},
                check, tag=f"gaps.{start // 6 + 1}",
            )
            for x in items(payload, "proposals"):
                control = next((c for c in batch if c["id"] == x.get("control_id")), None)
                if control is None or "shall" not in str(x.get("statement", "")).lower():
                    continue
                chunk = self._best_chunk(control, control["obligation"])
                proposals.append({
                    "statement": " ".join(str(x["statement"]).split()),
                    "acceptance_criteria": " ".join(str(x.get("acceptance_criteria", "")).split()),
                    "verification_method": x.get("verification_method") if x.get("verification_method")
                    in {"Test", "Demonstration", "Inspection", "Analysis"} else "Inspection",
                    "origin": "compliance_gap", "derived": True,
                    "type": "NFR", "actor": "system", "priority": "Must",
                    "risk_class": "Business-critical", "volatility": "Low",
                    "business_justification": f"Required by {control['citation']}: {control['obligation']}",
                    "source_statement_ids": [], "source_chunk_ids": [chunk["chunk_id"]] if chunk else [],
                    "invalid_chunk_ids": [], "evidence_quote": "", "assumptions": [], "dependencies": [],
                    "control_ids": [control["id"]], "regulations": [control["citation"]],
                })
        return proposals

    def commit_proposals(self, proposals: list[dict[str, Any]]) -> None:
        """Add ID-assigned gap proposals to the set and to the compliance matrix."""
        reqs = self.read("requirements", [])
        rows = self.read("compliance", [])
        gaps = self.read("gaps", [])
        for p in proposals:
            reqs.append(p)
            cid = p["control_ids"][0]
            rows.append({"req_id": p["req_id"], "control_id": cid, "citation": p["regulations"][0],
                         "relation": "satisfies", "evidence_chunk_id": (p["source_chunk_ids"] or [""])[0],
                         "rationale": "proposed to close a compliance gap", "similarity": None,
                         "needs_officer_approval": True, "status": "proposed"})
            gaps.append({"control_id": cid, "proposed_req_id": p["req_id"], "status": "proposed"})
        self.write("requirements", reqs)
        self.write("compliance", rows)
        # Whatever is still uncovered after the proposals is an open gap.
        for c in self.uncovered():
            gaps.append({"control_id": c["id"], "proposed_req_id": "", "status": "open"})
        self.write("gaps", gaps)
