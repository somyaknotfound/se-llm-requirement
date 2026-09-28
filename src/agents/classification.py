"""Classification agent: multi-label classification (brief point 9).

Every requirement gets all the categories that apply from the 13 in
config/pipeline.yaml. FR/NFR follows from the labels: a requirement is functional
exactly when "functional" is among its categories.

A deterministic keyword classifier backs the model up. It fills in when a
requirement comes back unlabelled, so a failed call never leaves a requirement
without categories, and its labels are recorded separately so the two can be
compared.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Agent, as_list, expect_list, items

CATEGORY_HELP = {
    "business": "a business or clinical goal or outcome the organisation wants",
    "stakeholder": "a need stated from a stakeholder's point of view",
    "functional": "a behaviour or function the system performs",
    "security": "authentication, authorisation, integrity, encryption, protection from attack",
    "privacy": "protection and appropriate use of personal and health information, consent",
    "regulatory": "an obligation imposed by law, regulation or certification",
    "performance": "response time, throughput, capacity",
    "availability_reliability": "uptime, fault tolerance, recovery, behaviour on failure",
    "usability": "ease of use, what users see, accessibility, clicks and time on task",
    "data_management": "what data is recorded, its content, quality and retention",
    "integration": "exchange with other systems, interfaces, message standards",
    "audit_reporting": "audit trails, logs, reports and their review",
    "operational": "running and maintaining the system: updates, monitoring, support",
}

KEYWORDS: dict[str, list[str]] = {
    "security": [r"authenticat", r"authori[sz]", r"\baccess\b", r"encrypt", r"password", r"token",
                 r"credential", r"session", r"\block\b", r"\btls\b", r"tamper", r"break-glass", r"sign(ing|ed)?\b"],
    "privacy": [r"consent", r"privacy", r"\bphi\b", r"health information", r"confidential",
                r"proxy", r"caregiver", r"care team", r"lock-screen|lock screen"],
    "regulatory": [r"regulat", r"certif", r"\bdea\b", r"hipaa", r"\bonc\b", r"\bcfr\b", r"complian",
                   r"third-party audit", r"attestation"],
    "performance": [r"within \d+(\.\d+)? ?(ms|milliseconds?|seconds?|s)\b", r"response time", r"latency",
                    r"per hour", r"\bload\b", r"within \d+ seconds"],
    "availability_reliability": [r"availab", r"uptime", r"99\.", r"\bfails?\b|failure|failed", r"outage",
                                 r"maintenance window|planned maintenance", r"recover", r"unavailable"],
    "usability": [r"screen", r"display", r"click", r"font", r"legib|readable", r"visible", r"notice",
                  r"under \d+ seconds"],
    "data_management": [r"retain|retention", r"\brecord(s|ed)?\b", r"archiv", r"\bstore", r"field",
                        r"dosage|strength|quantity"],
    "integration": [r"hl7", r"fhir", r"ncpdp", r"interface", r"intermediary", r"\bapi\b", r"gateway",
                    r"message", r"transmi", r"identity provider"],
    "audit_reporting": [r"\baudit", r"\blog(s|ged)?\b", r"report", r"review"],
    "operational": [r"updated? (at least )?(monthly|daily|weekly)", r"monitor", r"maintenance",
                    r"a/b test", r"time source", r"re-?audit"],
    "business": [r"eliminate", r"adoption", r"% of eligible", r"months of (go-live|launch)"],
    "functional": [r"shall (allow|display|send|check|calculate|notify|require|block|route|flag|let|prevent|"
                   r"publish|transmit|record|accept|cancel|generate|produce|show|include|remove|revoke|"
                   r"interrupt|limit|restrict|queue|provide|assign)"],
}


def keyword_categories(statement: str) -> list[str]:
    low = statement.lower()
    cats = [c for c, pats in KEYWORDS.items() if any(re.search(p, low) for p in pats)]
    return cats or ["functional"]


class ClassificationAgent(Agent):
    name = "classification"

    def classify(self, reqs: list[dict[str, Any]], key: str = "req_id") -> dict[str, list[str]]:
        """-> {requirement id: categories}. Batched; ids may be temporary."""
        categories = self.ctx.cfg["categories"]
        help_lines = "\n".join(f"{c}: {CATEGORY_HELP.get(c, '')}" for c in categories)
        out: dict[str, list[str]] = {}
        size = self.ctx.cfg["agents"]["batch_size"]

        for start in range(0, len(reqs), size):
            batch = reqs[start:start + size]
            ids = {r[key] for r in batch}
            table = "\n".join(f"{r[key]} | {r['statement']}" for r in batch)

            def check(p: Any, ids=ids) -> list[str]:
                errs = expect_list(p, "classifications", 1)
                got = {c.get("req_id") for c in items(p, "classifications")}
                missing = sorted(ids - got)
                if missing:
                    errs.append(f"no classification for {missing}")
                for c in items(p, "classifications"):
                    bad = [x for x in as_list(c.get("categories")) if x not in categories]
                    if bad:
                        errs.append(f"{c.get('req_id')}: unknown categories {bad}")
                return errs

            payload, _ = self.ask("classify", {"CATEGORIES": help_lines, "REQUIREMENTS": table},
                                  check, tag=f"classify.{start // size + 1}")
            for c in items(payload, "classifications"):
                cats = [x for x in as_list(c.get("categories")) if x in categories]
                if c.get("req_id") in ids and cats:
                    out[c["req_id"]] = list(dict.fromkeys(cats))

        for r in reqs:
            if r[key] not in out:
                out[r[key]] = keyword_categories(r["statement"])
                self.ctx.log(self.name, "keyword_fallback", req=r[key])
        return out

    @staticmethod
    def apply(req: dict[str, Any], cats: list[str]) -> dict[str, Any]:
        req["categories"] = cats
        req["keyword_categories"] = keyword_categories(req["statement"])
        req["type"] = "FR" if "functional" in cats else "NFR"
        return req
