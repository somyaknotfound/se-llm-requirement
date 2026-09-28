"""Security and privacy agent (brief points 10 and 11).

Threat-models the functionality with STRIDE against the requirement set and the
applicable security and privacy controls. Each threat records the requirements that
mitigate it; a threat nothing mitigates gets a proposed requirement, which goes to
the security officer for approval. Information-disclosure threats are privacy
threats as well as security ones.
"""

from __future__ import annotations

from typing import Any

from ..knowledge import applicable_controls
from .base import Agent, active, as_list, items

STRIDE = ["Spoofing", "Tampering", "Repudiation", "Information disclosure",
          "Denial of service", "Elevation of privilege"]


class SecurityPrivacyAgent(Agent):
    name = "security_privacy"

    def analyse(self) -> list[dict[str, Any]]:
        """Write the threat register; return proposals for unmitigated threats."""
        live = active(self.read("requirements", []))
        ids = {r["req_id"] for r in live}
        fn = self.ctx.case["functionality"]
        controls = [c for c in applicable_controls(self.ctx.case)
                    if set(c.get("category", [])) & {"security", "privacy"}]
        n = self.ctx.cfg["agents"].get("threats", 8)

        def check(p: Any) -> list[str]:
            errs = []
            threats = items(p, "threats")
            if len(threats) < 3:
                errs.append("list at least 3 threats")
            for t in threats:
                if t.get("stride") not in STRIDE:
                    errs.append(f"stride {t.get('stride')!r} is not one of {STRIDE}")
                unknown = [x for x in as_list(t.get("mitigated_by")) if x not in ids]
                if unknown:
                    errs.append(f"mitigated_by lists unknown requirement ids {unknown}")
            return errs

        payload, _ = self.ask(
            "threats",
            {"FUNCTIONALITY": f"{fn['name']}\n{fn['description'].strip()}",
             "REQUIREMENTS": "\n".join(f"{r['req_id']}: {r['statement']}" for r in live),
             "CONTROLS": "\n".join(f"{c['id']}: {c['title']} — {c['obligation']}" for c in controls),
             "N": str(n)},
            check, tag="stride",
        )
        threats = self.read("threats", [])
        proposals = []
        for t in items(payload, "threats"):
            if t.get("stride") not in STRIDE:
                continue
            tid = f"TH-{len(threats) + 1:02d}"
            mitigated = [x for x in as_list(t.get("mitigated_by")) if x in ids]
            threat = {"id": tid, "stride": t["stride"], "asset": str(t.get("asset", "")),
                      "description": str(t.get("description", "")), "mitigated_by": mitigated,
                      "proposed_req_id": ""}
            threats.append(threat)
            prop = t.get("proposed_requirement")
            if not mitigated and isinstance(prop, dict) and "shall" in str(prop.get("statement", "")).lower():
                privacy = t["stride"] == "Information disclosure"
                proposals.append({
                    "statement": " ".join(str(prop["statement"]).split()),
                    "acceptance_criteria": " ".join(str(prop.get("acceptance_criteria", "")).split()),
                    "verification_method": "Test", "origin": "security_threat", "derived": True,
                    "type": "NFR", "actor": "system", "priority": "Must",
                    "risk_class": "Business-critical", "volatility": "Low",
                    "business_justification": f"Mitigates {tid} ({t['stride']}): {threat['description']}",
                    "source_statement_ids": [], "source_chunk_ids": [], "invalid_chunk_ids": [],
                    "evidence_quote": "", "assumptions": [], "dependencies": [],
                    "categories": ["security", "privacy"] if privacy else ["security"],
                    "threat_id": tid,
                })
        self.write("threats", threats)
        return proposals

    def commit_proposals(self, proposals: list[dict[str, Any]]) -> None:
        reqs = self.read("requirements", [])
        threats = self.read("threats", [])
        by_threat = {t["id"]: t for t in threats}
        for p in proposals:
            reqs.append(p)
            if p.get("threat_id") in by_threat:
                by_threat[p["threat_id"]]["proposed_req_id"] = p["req_id"]
        self.write("requirements", reqs)
        self.write("threats", threats)
