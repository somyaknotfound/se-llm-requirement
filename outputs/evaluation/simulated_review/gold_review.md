# Gold-standard review by an LLM (not human review)

**Reviewer: Simulated reviewer (LLM), Claude Opus 5.5, 2026-11-25.** This is not the human review that
`reviewed_by` in `cases/<case>/gold.yaml` asks for. That field stays empty, and every gold-based
figure stays provisional. No gold requirement was changed: correcting the reference after seeing the
results would tune the evaluation. The reviewer knew the results when it reviewed.

Each gold requirement was read against the persona facts and documents it cites. A script also checked that
ids are unique, and that every cited fact, document and control exists and applies to the case: no errors.

| Case | Requirements | Supported | Concern | Possibly missing |
|---|---|---|---|---|
| epcs_signing | 35 | 23 | 12 | 2 |
| erx_issuance | 45 | 41 | 4 | 3 |
| refill_reminders | 28 | 26 | 2 | 3 |

Facts left uncovered are the losing side of a seeded conflict, explicitly out of scope, or listed as missing below.

## epcs_signing

| Id | Concern |
|---|---|
| G-EPCS-04 | 'For 95% of signings' is not in F-PRES-01, which says 'no more than 20 seconds'. |
| G-EPCS-07 | The cited F-COMP-04 does not mention an indication of readiness; the support is the control, 21 CFR 1311.120(b)(9)-(11). |
| G-EPCS-10 | The cited F-COMP-04 does not mention a time stamp; the support is the control, 21 CFR 1311.120(b)(14)-(16). |
| G-EPCS-11 | The cited F-PHARM-01 asks for a signed indication, not digital signing and archiving; the support is the control. |
| G-EPCS-13 | The cited F-PHARM-03 is about changes in transit; alteration after signing comes from the control, 1311.120(b)(19). |
| G-EPCS-15 | 1311.125 governs individual practitioners. A hospital credentialing office falls under 1311.130 (in the corpus, not in the control catalogue). |
| G-EPCS-16 | As G-EPCS-15: 1311.130 has the list approved by two individuals and entered separately, which is what DOC-CRED describes. |
| G-EPCS-17 | The audit finding also requires revocation on the day a practitioner leaves; that trigger is missing. |
| G-EPCS-19 | 1311.105 is for external credential providers; in-house proofing is 1311.110 (in the corpus, not in the catalogue). |
| G-EPCS-20 | As G-EPCS-19: the applicable section looks like 1311.110, not 1311.105. |
| G-EPCS-21 | As G-EPCS-19 for the cited control. |
| G-EPCS-25 | Covers the printed replacement; telling the prescriber that transmission failed (F-PRES-05) is not a requirement of its own. |

Possibly missing:

- Linking every DEA registration to the practitioner's account (CR-12 step 7); G-EPCS-09 covers only choosing one.
- Periodic review of signing permissions (IA-2025-07 recommendation 2).

## erx_issuance

| Id | Concern |
|---|---|
| G-ERX-02 | Merges two sources: the 1,200 orders/hour load comes from the architect, the 2 s target from the prescriber. Neither states them together. |
| G-ERX-05 | Covers interaction and allergy alerts only; the incident report also asks for a reason on duplicate-therapy overrides. |
| G-ERX-13 | Flagging is covered; the incident report's override reason for duplicate therapy is not. |
| G-ERX-33 | Omits the integrity protection in F-SEC-03 and the mutual TLS in DOC-INTERFACE. |

Possibly missing:

- Verbal orders are not permitted for outpatient prescriptions (MOP-7 3.2).
- Receiving Status, Error and Verify responses from the intermediary (DOC-INTERFACE).
- Quarterly releases through change control after go-live (F-PO-02) is uncovered; it may be a project constraint rather than a requirement.

## refill_reminders

| Id | Concern |
|---|---|
| G-REF-14 | Cites DOC-REVIEWS as support, but that review complains about being logged out on every app switch, so it pulls the other way. |
| G-REF-27 | An inference: DOC-API lists the gateway but does not say it is the only permitted destination. |

Possibly missing:

- Proxy access for patients aged 13-17 needs review by health information management (PP-3 item 6).
- SMART on FHIR patient scopes (DOC-API).
- Spacing of touch targets (DOC-REVIEWS).

## To complete the human review

1. Open `gold_review_sheet.csv` (one row per requirement, with the source text beside it).
2. Fill `human_verdict` (ok / change) and `human_note` for each row; start with the `concern` rows.
3. Put your name in `reviewed_by` in each `gold.yaml` and run `python -m src.evaluate --case all`.
