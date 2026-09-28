"""Validation layer — ISO/IEC/IEEE 29148 quality audit, hallucination audit, confidence.

    python -m src.validate rules          # rule-based scorer only (no model needed)
    python -m src.validate critic         # LLM-as-critic on a fresh context
    python -m src.validate hallucination  # citation verification against the corpus
    python -m src.validate confidence     # per-requirement confidence + review queue
    python -m src.validate all
    python -m src.validate all --case epcs_signing   # a case study's baseline set

Two independent scorers disagree in interesting places, and the disagreements are
the point. The rule-based scorer is mechanical and unforgiving; the LLM critic
reads for sense but is inconsistent. Neither is ground truth. Reporting their
agreement rate, and adjudicating a sample of conflicts by hand, is what turns
"the LLM produced some requirements" into a measured claim.

Two of the eight attributes — `necessary` and `feasible` — are only weakly
decidable by rule, and the heuristics here say so rather than quietly scoring 1.
That asymmetry is itself a finding: it marks exactly where a requirements engineer
is still doing the work.

Every scorer takes DataFrames, so the multi-agent validation agent runs exactly the
same checks on its requirement set as this driver runs on the baseline's.
"""

from __future__ import annotations

import argparse
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from . import load_pipeline, resolve
from .generate_reqs import guard_write, load_prompt, output_dir, render
from .ingest import load_chunks
from .llm import LLMError, OllamaClient

VALIDATION_COLUMNS = [
    "req_id",
    "attribute",
    "rule_score",
    "llm_score",
    "agreement",
    "human_adjudication",
    "note",
]

HALLUCINATION_COLUMNS = [
    "req_id",
    "cited_entity",
    "entity_type",
    "verdict",
    "evidence",
    "severity",
]

CONFIDENCE_COLUMNS = ["req_id", "confidence", "support", "quality", "escalate", "reasons"]

# Attributes a mechanical rule cannot honestly decide. Scored optimistically, but
# flagged in the note so the report never presents them as measured.
WEAKLY_DECIDABLE = {"necessary", "feasible"}

ABSOLUTE_CLAIMS = [
    "never fail",
    "never fails",
    "100% of the time",
    "zero downtime",
    "always available",
    "under all circumstances",
    "no downtime",
    "infinite",
    "instantaneous",
    "unlimited",
    "completely secure",
    "fully secure",
    "impossible to",
]

OBSERVABLE_MARKERS = [
    "return", "display", "record", "contain", "present", "reject", "log",
    "match", "equal", "within", "before", "after", "at least", "at most",
    "no more than", "fewer than", "greater than", "less than", "fail", "succeed",
    "prompt", "block", "prevent", "alert", "notify", "store", "transmit",
    "produce", "generate", "verify", "confirm", "deny", "grant", "shown",
]

COMPOUND_PATTERN = re.compile(
    r"\b(?:and|or)\s+(?:shall|must|also\s+)?(?:be\s+able\s+to\s+)?"
    r"(?:provide|record|display|generate|transmit|verify|log|store|alert|notify|"
    r"check|prevent|allow|enable|reject|retain|encrypt|authenticate|audit|send)\b",
    re.I,
)

# FHIR R4 resource names, used to tell a real-but-uncited resource (unverifiable)
# from an invented one (fabricated). Trimmed to the clinically relevant subset —
# a name outside this list is reported as unverifiable rather than fabricated so
# the audit never overclaims.
FHIR_R4_RESOURCES = {
    "AllergyIntolerance", "AuditEvent", "Basic", "Binary", "Bundle", "CarePlan",
    "CareTeam", "Claim", "ClinicalImpression", "Communication", "Composition",
    "Condition", "Consent", "Coverage", "Device", "DeviceRequest",
    "DiagnosticReport", "DocumentReference", "Encounter", "Endpoint", "Flag",
    "Goal", "Group", "HealthcareService", "ImagingStudy", "Immunization",
    "Location", "Measure", "Media", "Medication", "MedicationAdministration",
    "MedicationDispense", "MedicationKnowledge", "MedicationRequest",
    "MedicationStatement", "MessageHeader", "NutritionOrder", "Observation",
    "Organization", "Patient", "Person", "Practitioner", "PractitionerRole",
    "Procedure", "Provenance", "Questionnaire", "QuestionnaireResponse",
    "RelatedPerson", "RequestGroup", "RiskAssessment", "Schedule", "SearchParameter",
    "ServiceRequest", "Signature", "Slot", "Specimen", "Subscription", "Substance",
    "SupplyRequest", "Task", "ValueSet", "VerificationResult",
}


def _split(cell: Any) -> list[str]:
    return [c.strip() for c in str(cell or "").split(";") if c.strip() and c.strip() != "nan"]


def _is_true(cell: Any) -> bool:
    return str(cell).strip().lower() in {"true", "1", "yes"}


# --- corpus text for verification ----------------------------------------


@lru_cache(maxsize=1)
def _corpus_text() -> str:
    """Full processed corpus, normalised for substring checks.

    Uses processed/*.txt rather than the retrieved chunks: a citation can be
    correct and present in a source document even if that passage was never
    retrieved, and calling that 'fabricated' would be wrong.
    """
    proc_dir = resolve(load_pipeline()["paths"]["corpus_processed"])
    parts = [p.read_text(encoding="utf-8") for p in sorted(proc_dir.glob("*.txt"))]
    return _norm(" ".join(parts))


@lru_cache(maxsize=1)
def _chunks_by_id() -> dict[str, dict[str, Any]]:
    return {c["chunk_id"]: c for c in load_chunks()}


def _norm(text: str) -> str:
    text = text.replace("§", " ").replace("—", " ").replace("–", " ")
    return re.sub(r"\s+", " ", text).lower()


# --- 6.1 rule-based scorer -----------------------------------------------


def rule_score_requirement(
    req: dict[str, Any], all_statements: list[str], valid_chunk_ids: set[str]
) -> dict[str, tuple[int, str]]:
    cfg = load_pipeline()
    weak_words = cfg["validation"]["weak_words"]

    statement = str(req.get("statement", "") or "")
    ac = str(req.get("acceptance_criteria", "") or "")
    low = statement.lower()
    low_ac = ac.lower()
    cites = _split(req.get("source_chunk_ids"))
    invalid = _split(req.get("invalid_chunk_ids"))
    derived = _is_true(req.get("derived", ""))

    out: dict[str, tuple[int, str]] = {}

    # unambiguous
    found_weak = [w for w in weak_words if re.search(rf"\b{re.escape(w)}\b", low)]
    out["unambiguous"] = (
        (0, f"weak/vague term(s): {', '.join(found_weak[:4])}") if found_weak else (1, "no weak terms matched")
    )

    # singular
    shall_count = len(re.findall(r"\bshall\b", low))
    compound = COMPOUND_PATTERN.search(statement)
    if shall_count > 1:
        out["singular"] = (0, f"{shall_count} occurrences of 'shall'")
    elif ";" in statement:
        out["singular"] = (0, "semicolon suggests two obligations")
    elif compound:
        out["singular"] = (0, f"compound obligation near {compound.group(0)!r}")
    elif shall_count == 0:
        out["singular"] = (0, "no 'shall' — not stated as an obligation")
    else:
        out["singular"] = (1, "single 'shall', no compound obligation detected")

    # complete
    incompletes = [t for t in ("tbd", "tbc", "to be determined", "etc", "...") if t in low or t in low_ac]
    if not ac.strip():
        out["complete"] = (0, "acceptance_criteria is empty")
    elif incompletes:
        out["complete"] = (0, f"placeholder/open-ended token(s): {', '.join(incompletes)}")
    else:
        out["complete"] = (1, "no placeholders; acceptance criteria present")

    # verifiable
    weak_ac = [w for w in weak_words if re.search(rf"\b{re.escape(w)}\b", low_ac)]
    has_number = bool(re.search(r"\d", ac))
    has_marker = any(m in low_ac for m in OBSERVABLE_MARKERS)
    vm_ok = req.get("verification_method") in {"Test", "Demonstration", "Inspection", "Analysis"}
    if not ac.strip():
        out["verifiable"] = (0, "no acceptance criteria to verify against")
    elif not vm_ok:
        out["verifiable"] = (0, f"invalid verification_method {req.get('verification_method')!r}")
    elif weak_ac:
        out["verifiable"] = (0, f"acceptance criteria use vague term(s): {', '.join(weak_ac[:3])}")
    elif not (has_number or has_marker):
        out["verifiable"] = (0, "acceptance criteria state no observable outcome or threshold")
    else:
        out["verifiable"] = (1, "observable pass/fail condition present")

    # conforming
    if not re.search(r"\bshall\b", low):
        out["conforming"] = (0, "no 'shall'")
    elif not re.match(r"^\s*(the|a|an)\s+\w+", statement, re.I):
        out["conforming"] = (0, "statement does not open with an identified actor")
    elif re.search(r"\b(because|in order to|so that|rationale)\b", low):
        out["conforming"] = (0, "rationale mixed into the statement")
    else:
        out["conforming"] = (1, "declarative actor + shall form")

    # traceable
    unknown = [c for c in cites if c not in valid_chunk_ids]
    stakeholder_sources = _split(req.get("source_statement_ids"))
    if invalid:
        out["traceable"] = (0, f"cites chunk_id(s) it was never shown: {', '.join(invalid[:3])}")
    elif unknown:
        out["traceable"] = (0, f"cites unknown chunk_id(s): {', '.join(unknown[:3])}")
    elif cites:
        out["traceable"] = (1, f"cites {len(cites)} corpus chunk(s)")
    elif stakeholder_sources:
        out["traceable"] = (1, f"traces to {len(stakeholder_sources)} stakeholder statement(s)")
    elif derived:
        out["traceable"] = (1, "no citation but explicitly marked derived")
    else:
        out["traceable"] = (0, "no source_chunk_ids and derived=false")

    # necessary — weakly decidable
    others = [s for s in all_statements if s != statement]
    dup = _near_duplicate(statement, others)
    if dup:
        out["necessary"] = (0, f"near-duplicate of another requirement: {dup[:60]!r}")
    else:
        out["necessary"] = (1, "not a near-duplicate (rule cannot assess true necessity)")

    # feasible — weakly decidable
    absolutes = [a for a in ABSOLUTE_CLAIMS if a in low or a in low_ac]
    if absolutes:
        out["feasible"] = (0, f"absolute guarantee: {', '.join(absolutes[:2])}")
    else:
        out["feasible"] = (1, "no impossible absolute detected (rule cannot assess true feasibility)")

    return out


def _near_duplicate(statement: str, others: list[str], threshold: float = 0.8) -> str | None:
    tokens = set(re.findall(r"[a-z]+", statement.lower()))
    if not tokens:
        return None
    for other in others:
        otokens = set(re.findall(r"[a-z]+", other.lower()))
        if not otokens:
            continue
        jaccard = len(tokens & otokens) / len(tokens | otokens)
        if jaccard >= threshold:
            return other
    return None


def score_rules(reqs: pd.DataFrame) -> pd.DataFrame:
    cfg = load_pipeline()
    reqs = reqs.fillna("")
    valid_ids = set(_chunks_by_id())
    statements = [str(s) for s in reqs["statement"].tolist()]

    rows = []
    for _, r in reqs.iterrows():
        scored = rule_score_requirement(r.to_dict(), statements, valid_ids)
        for attr in cfg["validation"]["attributes"]:
            score, note = scored[attr]
            rows.append(
                {
                    "req_id": r["req_id"],
                    "attribute": attr,
                    "rule_score": score,
                    "rule_note": note,
                }
            )
    return pd.DataFrame(rows)


# --- 6.1 LLM-as-critic ----------------------------------------------------


def score_critic(
    reqs: pd.DataFrame, model_key: str = "primary", client: OllamaClient | None = None
) -> pd.DataFrame:
    cfg = load_pipeline()
    reqs = reqs.fillna("")
    attributes = cfg["validation"]["attributes"]
    template = load_prompt("p3_critic.txt")

    client = client or OllamaClient()
    client.require([model_key])

    rows = []
    for i, (_, r) in enumerate(reqs.iterrows(), start=1):
        print(f"[critic] {i}/{len(reqs)} {r['req_id']} ...", flush=True)
        prompt = render(
            template,
            REQ_ID=str(r["req_id"]),
            TYPE=str(r.get("type", "")),
            STATEMENT=str(r["statement"]),
            ACTOR=str(r.get("actor", "")),
            PRIORITY=str(r.get("priority", "")),
            VERIFICATION_METHOD=str(r.get("verification_method", "")),
            ACCEPTANCE_CRITERIA=str(r.get("acceptance_criteria", "")),
            RISK_CLASS=str(r.get("risk_class", "")),
            VOLATILITY=str(r.get("volatility", "")),
            SOURCE_CHUNK_IDS=str(r.get("source_chunk_ids", "")) or "(none)",
            DERIVED=str(r.get("derived", "")),
        )
        scores: dict[str, Any] = {}
        try:
            # Each requirement is judged in its own call, on a fresh context. A
            # single batched call would let the critic anchor on its earlier
            # verdicts and drift toward a uniform score.
            resp = client.generate(
                model_key,
                prompt=prompt,
                json_mode=True,
                tag="p3_critic",
                meta={"req_id": str(r["req_id"])},
            )
            scores = (resp.json() or {}).get("scores", {}) or {}
        except (LLMError, ValueError) as exc:
            print(f"          FAILED: {exc}")

        for attr in attributes:
            entry = scores.get(attr) or {}
            raw = entry.get("score") if isinstance(entry, dict) else entry
            try:
                val = int(raw)
                val = val if val in (0, 1) else None
            except (TypeError, ValueError):
                val = None
            rows.append(
                {
                    "req_id": r["req_id"],
                    "attribute": attr,
                    "llm_score": val,
                    "llm_note": (entry.get("note", "") if isinstance(entry, dict) else ""),
                }
            )
    return pd.DataFrame(rows)


def merge_scores(rules: pd.DataFrame, critic: pd.DataFrame | None) -> pd.DataFrame:
    if critic is None or critic.empty:
        merged = rules.copy()
        merged["llm_score"] = pd.NA
        merged["llm_note"] = ""
    else:
        merged = rules.merge(critic, on=["req_id", "attribute"], how="left")

    def agree(row) -> str:
        if pd.isna(row["llm_score"]):
            return "no_llm_score"
        return "agree" if int(row["rule_score"]) == int(row["llm_score"]) else "disagree"

    merged["agreement"] = merged.apply(agree, axis=1)
    merged["human_adjudication"] = ""
    merged["note"] = merged.apply(
        lambda r: f"rule: {r['rule_note']}"
        + (f" || llm: {r['llm_note']}" if str(r.get("llm_note", "")).strip() else ""),
        axis=1,
    )
    # Weakly-decidable attributes are labelled in place so nobody reading the CSV
    # mistakes an optimistic default for a measurement.
    merged.loc[merged["attribute"].isin(WEAKLY_DECIDABLE), "note"] = (
        "[rule weakly decidable] " + merged.loc[merged["attribute"].isin(WEAKLY_DECIDABLE), "note"]
    )
    return merged[VALIDATION_COLUMNS]


def write_adjudication_worksheet(merged: pd.DataFrame, out_dir: Path, limit: int = 12) -> int:
    """Pre-fill a worksheet of the conflicts most worth adjudicating by hand.

    human_adjudication is left blank in validation_29148.csv on purpose — filling
    it here would be fabricating a human judgement. This worksheet just puts the
    disagreements, both scores and both rationales side by side so the ~10
    adjudications the method calls for are a reading exercise, not a data hunt.
    """
    disagreements = merged[merged["agreement"] == "disagree"].copy()
    if disagreements.empty:
        return 0
    # Prioritise attributes where the two scorers are most likely to be
    # substantively rather than trivially at odds.
    priority = {"verifiable": 0, "unambiguous": 1, "singular": 2, "complete": 3,
                "conforming": 4, "traceable": 5, "necessary": 6, "feasible": 7}
    disagreements["_p"] = disagreements["attribute"].map(priority).fillna(9)
    disagreements = disagreements.sort_values(["_p", "req_id"]).head(limit)
    disagreements["human_adjudication"] = ""
    disagreements.drop(columns=["_p"]).to_csv(
        guard_write(out_dir / "adjudication_worksheet.csv"), index=False, encoding="utf-8"
    )
    return len(disagreements)


# --- 6.2 hallucination audit ---------------------------------------------

CFR_PATTERN = re.compile(r"\b(\d{1,2})\s*CFR\s*(?:§\s*)?(\d+\.\d+(?:\([a-z0-9]+\))*)", re.I)
BARE_SECTION_PATTERN = re.compile(r"§\s*(\d{2,4}\.\d+(?:\([a-z0-9]+\))*)")
STANDARD_PATTERN = re.compile(
    r"\b(ISO/IEC/IEEE|IEEE|ISO/IEC|ISO|NIST\s+SP|FIPS)\s*([\d]{2,5}(?:-[\d]+)?)", re.I
)
FHIR_TOKEN_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")

# CFR parts actually present in the corpus. A citation into one of these parts can
# be checked positively; a citation outside them cannot be resolved from what we
# hold, and is reported as unverifiable rather than assumed wrong.
CORPUS_CFR_PARTS = {"164", "170", "1311"}


def _severity(verdict: str, risk_class: str) -> str:
    if verdict == "fabricated":
        return "high" if risk_class == "Safety-critical" else "medium"
    if verdict == "misattributed":
        return "medium"
    if verdict == "unverifiable":
        return "low"
    return "none"


def audit_hallucinations(reqs: pd.DataFrame, reasoning: pd.DataFrame | None = None) -> pd.DataFrame:
    """Verify every regulatory, standards and corpus citation a requirement makes.

    `reasoning` is the baseline's separate reasoning file; the multi-agent set
    carries `reasoning` and `evidence_quote` on the requirement itself.
    """
    reqs = reqs.fillna("")
    corpus = _corpus_text()
    chunks = _chunks_by_id()

    reasoning_by_id: dict[str, dict[str, str]] = {}
    if reasoning is not None and not reasoning.empty:
        for _, r in reasoning.fillna("").iterrows():
            reasoning_by_id[str(r["req_id"])] = {
                "reasoning": str(r.get("reasoning", "")),
                "evidence_quote": str(r.get("evidence_quote", "")),
            }

    rows: list[dict[str, Any]] = []

    for _, r in reqs.iterrows():
        rid = str(r["req_id"])
        risk = str(r.get("risk_class", ""))
        extra = reasoning_by_id.get(rid) or {
            "reasoning": str(r.get("reasoning", "")),
            "evidence_quote": str(r.get("evidence_quote", "")),
        }
        haystack = " ".join(
            [
                str(r.get("statement", "")),
                str(r.get("acceptance_criteria", "")),
                extra.get("reasoning", ""),
                str(r.get("regulations", "")),
            ]
        )

        seen: set[tuple[str, str]] = set()

        for m in CFR_PATTERN.finditer(haystack):
            title, section = m.group(1), m.group(2)
            entity = f"{title} CFR {section}"
            if ("cfr", entity.lower()) in seen:
                continue
            seen.add(("cfr", entity.lower()))
            rows.append(_verdict_cfr(rid, entity, section, corpus, risk))

        for m in BARE_SECTION_PATTERN.finditer(haystack):
            section = m.group(1)
            entity = f"§ {section}"
            if ("cfr", entity.lower()) in seen:
                continue
            seen.add(("cfr", entity.lower()))
            rows.append(_verdict_cfr(rid, entity, section, corpus, risk))

        for m in STANDARD_PATTERN.finditer(haystack):
            entity = f"{m.group(1)} {m.group(2)}".strip()
            if ("std", entity.lower()) in seen:
                continue
            seen.add(("std", entity.lower()))
            present = _norm(entity) in corpus
            verdict = "verified" if present else "unverifiable"
            rows.append(
                {
                    "req_id": rid,
                    "cited_entity": entity,
                    "entity_type": "standard",
                    "verdict": verdict,
                    "evidence": "found in corpus text" if present
                    else "not in corpus; cannot be confirmed without the paywalled standard",
                    "severity": _severity(verdict, risk),
                }
            )

        # Whether a CamelCase token is a *claim about FHIR* depends on context.
        # Outside a FHIR context, only known resource names are treated as
        # citations — otherwise ordinary CamelCase prose would be audited. Inside
        # one, an unknown CamelCase token is exactly what a fabricated resource
        # name looks like, so it must not be filtered out before it is judged.
        # Naming a real resource alongside an unknown one ("uses MedicationRequest
        # and PrescriptionOrder") is itself the context signal — the second name is
        # being asserted as a resource just as much as the first.
        camel_tokens = {m.group(1) for m in FHIR_TOKEN_PATTERN.finditer(haystack)}
        fhir_context = bool(re.search(r"\bFHIR\b|\bresource\b", haystack, re.I)) or bool(
            camel_tokens & FHIR_R4_RESOURCES
        )
        for m in FHIR_TOKEN_PATTERN.finditer(haystack):
            token = m.group(1)
            if ("fhir", token) in seen:
                continue
            known = token in FHIR_R4_RESOURCES
            in_corpus = _norm(token) in corpus
            if not known and not in_corpus and not fhir_context:
                continue
            seen.add(("fhir", token))
            if in_corpus:
                verdict, evidence = "verified", "resource name present in corpus"
            elif known:
                verdict, evidence = "unverifiable", "real FHIR R4 resource but absent from corpus"
            else:
                verdict, evidence = (
                    "fabricated",
                    "named as a FHIR resource but is not a FHIR R4 resource and is absent from the corpus",
                )
            rows.append(
                {
                    "req_id": rid,
                    "cited_entity": token,
                    "entity_type": "fhir_resource",
                    "verdict": verdict,
                    "evidence": evidence,
                    "severity": _severity(verdict, risk),
                }
            )

        # The strongest single hallucination signal available: the model was told
        # to copy evidence_quote verbatim from a chunk it cited. A quote that is
        # not in the cited text is a fabricated attribution, not a paraphrase.
        quote = extra.get("evidence_quote", "").strip()
        if quote:
            cited = _split(r.get("source_chunk_ids"))
            cited_text = _norm(" ".join(chunks[c]["text"] for c in cited if c in chunks))
            nq = _norm(quote)
            if len(nq) < 12:
                verdict, evidence = "unverifiable", "quote too short to match reliably"
            elif nq in cited_text:
                verdict, evidence = "verified", "verbatim in a cited chunk"
            elif nq in corpus:
                verdict, evidence = "misattributed", "present in corpus but not in the cited chunk(s)"
            else:
                verdict, evidence = "fabricated", "not present anywhere in the corpus"
            rows.append(
                {
                    "req_id": rid,
                    "cited_entity": quote[:160],
                    "entity_type": "evidence_quote",
                    "verdict": verdict,
                    "evidence": evidence,
                    "severity": _severity(verdict, risk),
                }
            )

        for cid in _split(r.get("source_chunk_ids")):
            if cid not in chunks:
                rows.append(_fabricated_chunk(rid, cid, risk, "chunk_id does not exist in the corpus index"))

        # Citations the driver rejected because the model was never shown them.
        # They are either invented outright or guessed from the id pattern of
        # chunks it did see; both are fabricated attributions.
        for cid in _split(r.get("invalid_chunk_ids")):
            detail = (
                "exists in the corpus but was not among the evidence shown — the id was guessed"
                if cid in chunks
                else "chunk_id does not exist in the corpus index"
            )
            rows.append(_fabricated_chunk(rid, cid, risk, detail))

    return pd.DataFrame(rows, columns=HALLUCINATION_COLUMNS)


def _fabricated_chunk(rid: str, cid: str, risk: str, detail: str) -> dict[str, Any]:
    return {
        "req_id": rid,
        "cited_entity": cid,
        "entity_type": "chunk_id",
        "verdict": "fabricated",
        "evidence": detail,
        "severity": _severity("fabricated", risk),
    }


def _verdict_cfr(rid: str, entity: str, section: str, corpus: str, risk: str) -> dict[str, Any]:
    part = section.split(".")[0]
    base = section.split("(")[0]
    if _norm(base) in corpus:
        verdict, evidence = "verified", f"section {base} present in corpus text"
    elif part in CORPUS_CFR_PARTS:
        verdict, evidence = (
            "fabricated",
            f"CFR part {part} is in the corpus but section {base} does not appear in it",
        )
    else:
        verdict, evidence = (
            "unverifiable",
            f"CFR part {part} is outside the corpus; cannot be confirmed or refuted here",
        )
    return {
        "req_id": rid,
        "cited_entity": entity,
        "entity_type": "cfr_citation",
        "verdict": verdict,
        "evidence": evidence,
        "severity": _severity(verdict, risk),
    }


# --- confidence and escalation --------------------------------------------


def confidence_table(
    reqs: pd.DataFrame,
    merged: pd.DataFrame,
    audit: pd.DataFrame,
    conflicted: set[str] | None = None,
) -> pd.DataFrame:
    """Per-requirement confidence in [0, 1], with the reasons behind it.

    confidence = 0.5 * support + 0.5 * quality, then capped:

      support   1.0  evidence quote verified verbatim in a cited chunk, or the
                     requirement is corroborated by two or more stakeholders
                0.75 a valid citation or one stakeholder statement, quote unverified
                0.5  derived (inferred) with no citation — stated as an inference
                0.0  uncited and not derived
      quality   mean rule pass rate over the eight 29148 attributes, averaged with
                the critic's pass rate when the critic ran
      caps      0.3  any fabricated or misattributed citation or quote
                0.5  involved in an unresolved conflict or duplication

    It is a transparent heuristic, not a calibrated probability: there is no
    ground truth to calibrate against. Anything under the configured threshold,
    capped, or unsupported is escalated for human review.
    """
    threshold = load_pipeline()["validation"].get("confidence_threshold", 0.7)
    conflicted = conflicted or set()
    reqs = reqs.fillna("")

    bad_audit = audit[audit["verdict"].isin(["fabricated", "misattributed"])] if len(audit) else audit
    bad_ids = set(bad_audit["req_id"].astype(str)) if len(bad_audit) else set()
    verified_quote = set()
    if len(audit):
        vq = audit[(audit["entity_type"] == "evidence_quote") & (audit["verdict"] == "verified")]
        verified_quote = set(vq["req_id"].astype(str))

    rows = []
    for _, r in reqs.iterrows():
        rid = str(r["req_id"])
        cites = _split(r.get("source_chunk_ids"))
        stakeholders = {s.split("-")[1] if s.count("-") >= 2 else s
                        for s in _split(r.get("source_statement_ids"))}
        derived = _is_true(r.get("derived"))
        reasons: list[str] = []

        if rid in verified_quote or len(stakeholders) >= 2:
            support = 1.0
        elif cites or stakeholders:
            support = 0.75
        elif derived:
            support = 0.5
            reasons.append("derived with no citation or stakeholder source")
        else:
            support = 0.0
            reasons.append("unsupported: no valid citation, no stakeholder source, not derived")

        sub = merged[merged["req_id"].astype(str) == rid]
        rule_q = float(sub["rule_score"].mean()) if len(sub) else 0.0
        llm_scores = pd.to_numeric(sub["llm_score"], errors="coerce").dropna() if len(sub) else []
        quality = (rule_q + float(llm_scores.mean())) / 2 if len(llm_scores) else rule_q
        failed = sub[sub["rule_score"] == 0]["attribute"].tolist() if len(sub) else []
        if failed:
            reasons.append("29148 rule failures: " + ", ".join(failed))

        conf = 0.5 * support + 0.5 * quality
        if rid in bad_ids:
            conf = min(conf, 0.3)
            reasons.append("fabricated or misattributed citation")
        if rid in conflicted:
            conf = min(conf, 0.5)
            reasons.append("unresolved conflict or duplication")
        if _split(r.get("invalid_chunk_ids")):
            conf = min(conf, 0.3)
            reasons.append("cited evidence it was never shown")

        escalate = conf < threshold or support == 0.0
        rows.append(
            {
                "req_id": rid,
                "confidence": round(conf, 3),
                "support": support,
                "quality": round(quality, 3),
                "escalate": escalate,
                "reasons": "; ".join(reasons),
            }
        )
    return pd.DataFrame(rows, columns=CONFIDENCE_COLUMNS)


def review_queue(conf: pd.DataFrame, reqs: pd.DataFrame) -> pd.DataFrame:
    """Every requirement awaits human approval; escalated ones are listed first.

    The decision columns are left blank. Accept, reject, modify and regenerate are
    human actions and are recorded by the approval tooling, never filled here.
    """
    q = conf.merge(reqs[["req_id", "statement"]], on="req_id", how="left")
    q["approval_status"] = "pending"
    q["human_decision"] = ""
    q["human_note"] = ""
    return q.sort_values(["escalate", "confidence"], ascending=[False, True])


# --- driver ---------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Validation layer")
    ap.add_argument("stage", choices=["rules", "critic", "hallucination", "confidence", "all"])
    ap.add_argument("--model", default="primary", choices=["primary", "secondary"])
    ap.add_argument("--case", default=None, help="validate a case study's baseline set")
    args = ap.parse_args()

    out_dir = output_dir(args.case)
    req_path = out_dir / "requirements.csv"
    if not req_path.exists():
        raise SystemExit(f"{req_path} missing — run Part 1 first.")
    reqs = pd.read_csv(req_path).fillna("")
    reasoning_path = out_dir / "requirements_reasoning.csv"
    reasoning = pd.read_csv(reasoning_path).fillna("") if reasoning_path.exists() else None

    merged = None
    if args.stage in ("rules", "critic", "all"):
        rules = score_rules(reqs)
        print(f"[rules] scored {len(reqs)} requirements x {rules['attribute'].nunique()} attributes")
        critic = None
        if args.stage in ("critic", "all"):
            try:
                critic = score_critic(reqs, args.model)
            except LLMError as exc:
                print(f"[critic] unavailable: {exc}")
                print("[critic] writing rule-only scores; llm_score will be blank")

        merged = merge_scores(rules, critic)
        merged.to_csv(
            guard_write(out_dir / "validation_29148.csv"), index=False, encoding="utf-8"
        )

        scored = merged[merged["agreement"] != "no_llm_score"]
        if len(scored):
            rate = (scored["agreement"] == "agree").mean()
            print(f"\n[validate] scorer agreement: {rate:.1%} over {len(scored)} judgements")
            n = write_adjudication_worksheet(merged, out_dir)
            print(f"[validate] {n} conflicts written to adjudication_worksheet.csv for manual review")
        print("[validate] wrote validation_29148.csv")

        pass_rate = merged.groupby("attribute")["rule_score"].mean().sort_values()
        print("\n[validate] rule-based pass rate per attribute:")
        for attr, val in pass_rate.items():
            flag = "  (weakly decidable)" if attr in WEAKLY_DECIDABLE else ""
            print(f"           {attr:<14} {val:.0%}{flag}")

    audit = None
    if args.stage in ("hallucination", "all"):
        audit = audit_hallucinations(reqs, reasoning)
        audit.to_csv(
            guard_write(out_dir / "hallucination_audit.csv"), index=False, encoding="utf-8"
        )
        print(f"\n[hallucination] {len(audit)} citation(s) checked")
        if len(audit):
            for verdict, n in audit["verdict"].value_counts().items():
                print(f"           {verdict:<15} {n}")
            bad = audit[audit["verdict"].isin(["fabricated", "misattributed"])]
            if len(bad):
                print(f"\n[hallucination] {len(bad)} suspect citation(s) — lead the discussion with these:")
                for _, r in bad.head(8).iterrows():
                    print(f"           {r['req_id']} [{r['verdict']}] {str(r['cited_entity'])[:70]}")
        print("[hallucination] wrote hallucination_audit.csv")

    if args.stage in ("confidence", "all"):
        if merged is None:
            merged = pd.read_csv(out_dir / "validation_29148.csv")
        if audit is None:
            audit = pd.read_csv(out_dir / "hallucination_audit.csv").fillna("")
        conf = confidence_table(reqs, merged, audit)
        queue = review_queue(conf, reqs)
        queue.to_csv(guard_write(out_dir / "review_queue.csv"), index=False, encoding="utf-8")
        n_esc = int(conf["escalate"].sum())
        print(f"\n[confidence] mean {conf['confidence'].mean():.2f}; "
              f"{n_esc}/{len(conf)} escalated for human review -> review_queue.csv")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
