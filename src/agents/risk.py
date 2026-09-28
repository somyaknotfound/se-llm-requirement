"""Risk-analysis agent (brief point 4): the risk register.

The model rates likelihood and impact per requirement; the level is computed
deterministically from their product, so the banding is auditable and the same
everywhere:

    score = likelihood x impact   >= 15 Critical   >= 10 High   >= 5 Medium   else Low

A requirement's risk level is its highest risk. Critical and High clinical-safety
risks mark the requirement safety-critical and route it to the clinical safety
officer for approval.
"""

from __future__ import annotations

from typing import Any

from .base import Agent, active, items

CATEGORIES = {"clinical_safety", "security", "privacy", "compliance", "technical", "business", "operational"}
ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


def level(likelihood: int, impact: int) -> str:
    score = likelihood * impact
    if score >= 15:
        return "Critical"
    if score >= 10:
        return "High"
    if score >= 5:
        return "Medium"
    return "Low"


def _int(value: Any) -> int | None:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    return v if 1 <= v <= 5 else None


class RiskAnalysisAgent(Agent):
    name = "risk_analysis"

    def run(self) -> dict[str, int]:
        reqs = self.read("requirements", [])
        live = active(reqs)
        threats = self.read("threats", [])
        threat_lines = "\n".join(f"{t['id']} ({t['stride']}): {t['description']}" for t in threats) or "none"
        risks = self.read("risks", [])
        size = self.ctx.cfg["agents"]["batch_size"]

        for start in range(0, len(live), size):
            batch = live[start:start + size]
            ids = {r["req_id"] for r in batch}

            def check(p: Any, ids=ids) -> list[str]:
                errs = []
                got = {x.get("req_id") for x in items(p, "risks")}
                errs += [f"no risk for {rid}" for rid in sorted(ids - got)]
                for x in items(p, "risks"):
                    if x.get("category") not in CATEGORIES:
                        errs.append(f"{x.get('req_id')}: category must be one of {sorted(CATEGORIES)}")
                    if _int(x.get("likelihood")) is None or _int(x.get("impact")) is None:
                        errs.append(f"{x.get('req_id')}: likelihood and impact must be integers 1-5")
                return errs

            payload, _ = self.ask(
                "risk",
                {"REQUIREMENTS": "\n".join(f"{r['req_id']} [{r.get('risk_class', '')}]: {r['statement']}"
                                           for r in batch),
                 "THREATS": threat_lines},
                check, tag=f"risk.{start // size + 1}",
            )
            for x in items(payload, "risks"):
                lk, im = _int(x.get("likelihood")), _int(x.get("impact"))
                if x.get("req_id") not in ids or lk is None or im is None or x.get("category") not in CATEGORIES:
                    continue
                risks.append({"id": f"RK-{len(risks) + 1:02d}", "req_id": x["req_id"],
                              "category": x["category"], "description": str(x.get("description", "")),
                              "likelihood": lk, "impact": im, "score": lk * im, "level": level(lk, im),
                              "mitigation": str(x.get("mitigation", ""))})

        worst: dict[str, dict[str, Any]] = {}
        for rk in risks:
            cur = worst.get(rk["req_id"])
            if cur is None or ORDER[rk["level"]] > ORDER[cur["level"]]:
                worst[rk["req_id"]] = rk
        for r in live:
            rk = worst.get(r["req_id"])
            r["risk_level"] = rk["level"] if rk else "Unassessed"
            if rk and rk["category"] == "clinical_safety" and ORDER[rk["level"]] >= ORDER["High"]:
                r["risk_class"] = "Safety-critical"
        self.write("risks", risks)
        self.write("requirements", reqs)
        return {"risks": len(risks), "high_or_critical": sum(1 for rk in risks if ORDER[rk["level"]] >= 2)}
