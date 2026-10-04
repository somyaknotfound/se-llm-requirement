# Generated tables

_Regenerate with `python -m src.report`._

## Corpus manifest

| doc_id | title | publisher | year | license | doc_type | n_chunks |
|---|---|---|---|---|---|---|
| D01 | HL7 FHIR R4 — MedicationRequest Resource | Health Level Seven International | 2019 | CC0-1.0 | interoperability_standard | 23 |
| D02 | HL7 FHIR R4 — AllergyIntolerance Resource | Health Level Seven International | 2019 | CC0-1.0 | interoperability_standard | 24 |
| D03 | HL7 FHIR R4 — Security and Privacy Module | Health Level Seven International | 2019 | CC0-1.0 | interoperability_standard | 17 |
| D04 | HIPAA Security Rule — 45 CFR Part 164 Subpart C (Security Standards) | U.S. Office of the Federal Register (eCFR) | 2025 | US-Gov-Public-Domain | regulation | 10 |
| D05 | ONC Health IT Certification Criteria — 45 CFR 170.315 | U.S. Office of the Federal Register (eCFR) | 2025 | US-Gov-Public-Domain | regulation | 29 |
| D06 | DEA Electronic Prescriptions for Controlled Substances — 21 CFR Part 1311 | U.S. Office of the Federal Register (eCFR) | 2025 | US-Gov-Public-Domain | regulation | 45 |

## Requirements

| req_id | type | nfr_category | statement | priority | risk_class | volatility | derived |
|---|---|---|---|---|---|---|---|
| FR-01 | FR | none | The system shall allow a prescriber to issue an electronic prescription for a patient. | Must | Safety-critical | Low | False |
| FR-02 | FR | none | The system shall perform real-time drug-drug interaction and allergy contraindication checking at the point of ordering. | Must | Safety-critical | Low | False |
| FR-03 | FR | none | The system shall ensure that controlled-substance prescriptions are signed by an authorized prescriber using two-factor authentication. | Must | Safety-critical | Low | False |
| FR-04 | FR | none | The system shall transmit the signed controlled-substance prescription to a pharmacy without the digital signature. | Must | Safety-critical | Low | False |
| FR-05 | FR | none | The system shall generate an audit record for each action related to the issuance of a controlled-substance prescription. | Must | Safety-critical | Low | False |
| FR-06 | FR | none | The system shall ensure that the audit records are protected from unauthorized deletion and modifications. | Must | Safety-critical | Low | False |
| FR-07 | FR | none | The system shall retain all archived records electronically for at least two years from the date of their receipt or creation. | Must | Safety-critical | Low | False |
| FR-08 | FR | none | The system shall allow the prescriber to cancel or change an existing electronic prescription. | Must | Safety-critical | Low | False |
| FR-09 | FR | none | The system shall ensure that the patient's demographic and observation data are recorded, including race, ethnicity, preferred language, sex, sexual orientation, gender identity, name to use, pronouns, and date of birth. | Must | Safety-critical | Low | False |
| FR-10 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted to the pharmacy within 2 seconds for 95% of requests under a load of 50 concurrent prescribers. | Must | Performance | Low | False |
| FR-11 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted to the pharmacy without any alteration or truncation of data during transmission. | Must | Safety-critical | Low | False |
| FR-12 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted in its original electronic form and not converted to another form during transmission. | Must | Safety-critical | Low | False |
| FR-13 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted only after an original prescription has not been printed. | Must | Safety-critical | Low | False |
| FR-14 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted only if it has been signed by an authorized prescriber. | Must | Safety-critical | Low | False |
| FR-15 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted to the designated pharmacy only. | Must | Safety-critical | Low | False |
| FR-16 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted in a format that can be read and processed by the pharmacy application. | Must | Safety-critical | Low | False |
| FR-17 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted in a secure manner to prevent unauthorized access. | Must | Safety-critical | Low | False |
| FR-18 | FR | none | The system shall ensure that the controlled-substance prescription is transmitted in a manner that complies with all applicable regulations and standards. | Must | Safety-critical | Low | False |

## Per-requirement reasoning (sample)

| req_id | inference_type | reasoning |
|---|---|---|
| FR-01 | direct_extraction | This requirement is directly derived from the source evidence which states that the system covers all types of medication orders for a patient, including electronic prescriptions. |
| FR-02 | direct_extraction | The evidence explicitly states that drug-drug and drug-allergy interaction checks must be performed before a medication order is completed. |
| FR-03 | direct_extraction | The evidence mandates that the prescriber must complete a two-factor authentication protocol to use their private key for signing controlled-substance prescriptions. |
| FR-04 | direct_extraction | The evidence states that the electronic prescription must be transmitted in its electronic form, and it may not include a digital signature. |
| FR-05 | generalization | The evidence mandates that the system must maintain an audit trail of all actions related to the issuance of controlled-substance prescriptions. |
| FR-06 | direct_extraction | The evidence states that the audit records must be protected from unauthorized deletion and modifications. |

## Metrics summary

| section | metric | value | detail |
|---|---|---|---|
| corpus | source_documents | 6 | D01; D02; D03; D04; D05; D06 |
| corpus | corpus_bytes | 1062330 | raw downloaded bytes |
| corpus | chunks | 148 | tokenizer=cl100k_base |
| corpus | chunk_tokens_total | 71111 |  |
| corpus | chunk_tokens_mean | 480.5 |  |
| part1 | requirements_total | 18 |  |
| part1 | requirements_fr | 18 |  |
| part1 | requirements_nfr | 0 | target >= 8 |
| part1 | traceability_rate | 1.0 | share citing >=1 chunk_id; target >= 0.7 |
| part1 | derived_rate | 0.0 | share marked derived=true |
| part1 | documents_cited | 3 | D01; D05; D06 |
| part1 | documents_uncited | 3 | D02; D03; D04 |
| part1 | integrity_violations | 0 | rows with no citation AND derived=false — kept, flagged and escalated |
| part1 | guessed_chunk_citations | 0 | requirements citing a chunk_id the model was never shown |
| part1 | repair_attempted | 1 | response used: initial_after_failed_repair; initial errors: 2 |
| part1 | contract_passed | 0 | only 0 NFRs; contract requires at least 8; FR-10: risk_class='Performance' is not one of ['Business-critical', 'Safety-critical', 'Standard'] |
| part1 | nfr_categories | 0 | {} |
| part1 | risk_class_distribution |  | {'Safety-critical': 17, 'Performance': 1} |
| part1 | volatility_distribution |  | {'Low': 18} |
| part1 | priority_distribution |  | {'Must': 18} |
| validation | pass_rate_complete | 1.0 | rule=100%, llm=100% |
| validation | pass_rate_conforming | 1.0 | rule=100%, llm=100% |
| validation | pass_rate_feasible | 1.0 | rule=100%, llm=100% |
| validation | pass_rate_necessary | 1.0 | rule=100%, llm=100% |
| validation | pass_rate_singular | 1.0 | rule=100%, llm=100% |
| validation | pass_rate_traceable | 1.0 | rule=100%, llm=100% |
| validation | pass_rate_unambiguous | 1.0 | rule=100%, llm=0% |
| validation | pass_rate_verifiable | 0.667 | rule=67%, llm=0% |
| validation | scorer_agreement | 0.792 | 144 judgements compared |
| validation | scorer_agreement_by_attribute |  | {'complete': 1.0, 'conforming': 1.0, 'feasible': 1.0, 'necessary': 1.0, 'singular': 1.0, 'traceable': 1.0, 'unambiguous': 0.0, 'verifiable': 0.33} |
| validation | disagreements | 30 |  |
| validation | human_adjudicated | 0 | conflicts resolved by hand |
| hallucination | citations_checked | 17 | {'verified': 15, 'misattributed': 1, 'fabricated': 1} |
| hallucination | fabricated | 1 |  |
| hallucination | misattributed | 1 |  |
| hallucination | unverifiable | 0 |  |
| hallucination | hallucination_rate | 0.118 | (fabricated + misattributed) / citations checked |
| hallucination | high_severity | 1 | fabricated citation on a safety-critical requirement |
| hallucination | suspect_by_entity_type |  | {'evidence_quote': 2} |
| part2 | runs_total | 18 |  |
| part2 | runs_with_recommendation | 18 |  |
| part2 | modal_recommendation | Agile | {'Agile': 12, 'Waterfall': 3, 'V-Model': 3} |
| part2 | modal_share | 0.667 | share of runs choosing the modal model |
| part2 | framing_flip_rate | 1.0 | 6/6 (model,trial) groups changed answer across framings |
| part2 | cross_model_agreement | 0.667 | 6/9 (framing,trial) pairs where both models agreed |
| part2 | recommendation_agile_primed |  | {'Agile': 6} |
| part2 | recommendation_neutral |  | {'Agile': 6} |
| part2 | recommendation_plan_primed |  | {'Waterfall': 3, 'V-Model': 3} |
| part2 | grounding_rate | 0.979 | criterion justifications citing >=1 req_id vs generic SE reasoning |
| part2 | grounding_rate_valid_ids | 0.803 | justifications where every cited req_id exists in outputs/cases/erx_issuance/requirements.csv |
| part2 | criterion_mean_scores |  | {'change_frequency': 2.0, 'continuous_delivery_need': 3.0, 'documentation_rigour': 4.28, 'failure_consequence': 4.83, 'formal_verification_need': 4.56, 'legacy_dependence': 2.22, 'project_complexity': 3.78, 'regulatory_criticality': 4.72, 'requirement_instability': 2.39, 'schedule_budget_rigidity': 4.33, 'security_risk': 4.83, 'stakeholder_availability': 4.28, 'system_size': 3.22} |
| part2 | engine_consistency | 0.056 | runs whose named model is the one their own factor scores imply (rules + MCDA) |
| eval:epcs_signing:multi_agent | precision | 0.373 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | recall | 0.886 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | f1 | 0.525 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | precision_elicited | 0.419 | 31/74 stakeholder- and document-sourced requirements matched (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | requirements_generated | 83 | gold has 35; by origin {'compliance_gap': 9, 'document': 18, 'stakeholder': 56} (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | category_agreement | 0.366 | mean Jaccard of categories on matched pairs (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | ambiguity_detection_recall | 0.833 | 5/6 seeded vague facts followed up; missed: ['F-SEC-01'] (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | conflict_detection_recall | 0.0 | 0/3 seeded conflicts found; 15 conflicts flagged; missed: ['C-EPCS-01', 'C-EPCS-02', 'C-EPCS-03']; both sides reached the requirements for 3/3 (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | conflict_detection_precision | 0.0 | 0/3 seeded conflicts found; 15 conflicts flagged; missed: ['C-EPCS-01', 'C-EPCS-02', 'C-EPCS-03']; both sides reached the requirements for 3/3 (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | control_coverage | 1.0 | 33/33 applicable controls |
| eval:epcs_signing:multi_agent | gold_control_coverage | 1.0 | 18/18 controls the gold requirements satisfy (gold not yet reviewed — provisional) |
| eval:epcs_signing:multi_agent | hallucination_rate | 0.054 | 221 citations checked |
| eval:epcs_signing:multi_agent | citation_correctness | 0.73 | share of 37 evidence quotes verbatim in the cited chunk |
| eval:epcs_signing:multi_agent | quality_first_draft | 0.895 | 29148 rule pass rate before clarification |
| eval:epcs_signing:multi_agent | quality_final | 0.905 | 29148 rule pass rate after clarification |
| eval:epcs_signing:multi_agent | traceability_coverage | 1.0 | requirements traceable to a stakeholder statement or corpus chunk |
| eval:epcs_signing:multi_agent | mean_confidence | 0.73 |  |
| eval:epcs_signing:multi_agent | escalated | 22 | requirements escalated for review |
| eval:epcs_signing:multi_agent | agent_calls_failed_after_repair | 12 | of 165 agent calls; ['extract.document-DOC-CRED-policy', 'extract.document-DOC-FINDING-audit-finding', 'extract.document-DOC-KICKOFF-meeting-notes', 'extract.document-DOC-VENDOR-email', 'factors.primary', 'factors.secondary', 'map.1', 'map.12', 'map.15', 'map.4', 'revise.NFR-EPCS-019', 'stride'] |
| eval:epcs_signing:multi_agent | sdlc_recommendation | Waterfall | 87.5%; runner-up V-Model |
| eval:epcs_signing:multi_agent | sdlc_top1 |  | expert SDLC choice not yet recorded in gold.yaml |
| eval:epcs_signing:multi_agent | human_correction_rate |  | no human decisions recorded yet |
| eval:epcs_signing:multi_agent | processing_minutes | 93.7 | wall-clock, all steps |
| eval:epcs_signing:multi_agent | time_saved_vs_manual |  | manual effort not recorded in gold.yaml |
| eval:epcs_signing:multi_agent | injection_quarantined:INJ-EPCS-01 | 1 | the scanner quarantined the seeded injection before any agent saw it |
| eval:epcs_signing:baseline | precision | 0.611 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:epcs_signing:baseline | recall | 0.314 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:epcs_signing:baseline | f1 | 0.415 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:epcs_signing:baseline | requirements_generated | 18 | gold has 35 (gold not yet reviewed — provisional) |
| eval:epcs_signing:baseline | control_coverage | 0.485 | 16/33 applicable controls — upper bound: any cited chunk in the control's section counts |
| eval:epcs_signing:baseline | hallucination_rate | 0.0 | 1 citations checked |
| eval:epcs_signing:baseline | citation_correctness | 1.0 | share of 1 evidence quotes verbatim in the cited chunk |
| eval:epcs_signing:baseline | quality_final | 0.944 | 29148 rule pass rate (no clarification loop) |
| eval:epcs_signing:baseline | traceability_coverage | 1.0 | requirements citing a corpus chunk |
| eval:epcs_signing:baseline | ambiguity_detection_recall | 0.0 | no stakeholder interaction, by construction (gold not yet reviewed — provisional) |
| eval:epcs_signing:baseline | conflict_detection_recall | 0.0 | no conflict detection step, by construction (gold not yet reviewed — provisional) |
| eval:epcs_signing:baseline | processing_minutes | 5.7 | model time for the Part 1 calls |
| eval:epcs_signing:multi_agent | stakeholder_satisfaction_sus |  | no survey responses recorded |
| eval:erx_issuance:multi_agent | precision | 0.651 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | recall | 0.622 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | f1 | 0.636 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | precision_elicited | 0.778 | 28/36 stakeholder- and document-sourced requirements matched (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | requirements_generated | 43 | gold has 45; by origin {'compliance_gap': 7, 'document': 6, 'stakeholder': 30} (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | category_agreement | 0.506 | mean Jaccard of categories on matched pairs (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | ambiguity_detection_recall | 0.857 | 6/7 seeded vague facts followed up; missed: ['F-PHARM-04'] (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | conflict_detection_recall | 0.0 | 0/3 seeded conflicts found; 5 conflicts flagged; missed: ['C-ERX-01', 'C-ERX-02', 'C-ERX-03']; both sides reached the requirements for 0/3 (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | conflict_detection_precision | 0.0 | 0/3 seeded conflicts found; 5 conflicts flagged; missed: ['C-ERX-01', 'C-ERX-02', 'C-ERX-03']; both sides reached the requirements for 0/3 (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | control_coverage | 1.0 | 28/28 applicable controls |
| eval:erx_issuance:multi_agent | gold_control_coverage | 1.0 | 19/19 controls the gold requirements satisfy (gold not yet reviewed — provisional) |
| eval:erx_issuance:multi_agent | hallucination_rate | 0.029 | 104 citations checked |
| eval:erx_issuance:multi_agent | citation_correctness | 0.625 | share of 8 evidence quotes verbatim in the cited chunk |
| eval:erx_issuance:multi_agent | quality_first_draft | 0.924 | 29148 rule pass rate before clarification |
| eval:erx_issuance:multi_agent | quality_final | 0.942 | 29148 rule pass rate after clarification |
| eval:erx_issuance:multi_agent | traceability_coverage | 1.0 | requirements traceable to a stakeholder statement or corpus chunk |
| eval:erx_issuance:multi_agent | mean_confidence | 0.745 |  |
| eval:erx_issuance:multi_agent | escalated | 9 | requirements escalated for review |
| eval:erx_issuance:multi_agent | agent_calls_failed_after_repair | 11 | of 104 agent calls; ['extract.document-DOC-EMAIL-email', 'extract.document-DOC-INCIDENT-incident-report', 'extract.document-DOC-INTERFACE-legacy-system-spe', 'extract.document-DOC-KICKOFF-meeting-notes', 'extract.document-DOC-POLICY-policy', 'extract.stakeholder-architect-ARCH', 'extract.stakeholder-clinical-safety-officer-CSO', 'extract.stakeholder-pharmacist-PHARM', 'extract.stakeholder-product-owner-PO', 'extract.stakeholder-security-officer-SEC', 'stride'] |
| eval:erx_issuance:multi_agent | sdlc_recommendation | Waterfall | 79.2%; runner-up V-Model |
| eval:erx_issuance:multi_agent | sdlc_top1 |  | expert SDLC choice not yet recorded in gold.yaml |
| eval:erx_issuance:multi_agent | human_correction_rate |  | no human decisions recorded yet |
| eval:erx_issuance:multi_agent | processing_minutes | 68.8 | wall-clock, all steps |
| eval:erx_issuance:multi_agent | time_saved_vs_manual |  | manual effort not recorded in gold.yaml |
| eval:erx_issuance:multi_agent | injection_quarantined:INJ-ERX-01 | 1 | the scanner quarantined the seeded injection before any agent saw it |
| eval:erx_issuance:baseline | precision | 0.312 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:erx_issuance:baseline | recall | 0.111 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:erx_issuance:baseline | f1 | 0.164 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:erx_issuance:baseline | requirements_generated | 16 | gold has 45 (gold not yet reviewed — provisional) |
| eval:erx_issuance:baseline | control_coverage | 0.357 | 10/28 applicable controls — upper bound: any cited chunk in the control's section counts |
| eval:erx_issuance:baseline | hallucination_rate | 0.312 | 16 citations checked |
| eval:erx_issuance:baseline | citation_correctness | 0.688 | share of 16 evidence quotes verbatim in the cited chunk |
| eval:erx_issuance:baseline | quality_final | 0.953 | 29148 rule pass rate (no clarification loop) |
| eval:erx_issuance:baseline | traceability_coverage | 1.0 | requirements citing a corpus chunk |
| eval:erx_issuance:baseline | ambiguity_detection_recall | 0.0 | no stakeholder interaction, by construction (gold not yet reviewed — provisional) |
| eval:erx_issuance:baseline | conflict_detection_recall | 0.0 | no conflict detection step, by construction (gold not yet reviewed — provisional) |
| eval:erx_issuance:baseline | processing_minutes | 6.2 | model time for the Part 1 calls |
| eval:erx_issuance:multi_agent | stakeholder_satisfaction_sus |  | no survey responses recorded |
| eval:refill_reminders:multi_agent | precision | 0.29 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | recall | 0.643 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | f1 | 0.4 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | precision_elicited | 0.353 | 18/51 stakeholder- and document-sourced requirements matched (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | requirements_generated | 62 | gold has 28; by origin {'compliance_gap': 11, 'document': 19, 'stakeholder': 32} (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | category_agreement | 0.509 | mean Jaccard of categories on matched pairs (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | ambiguity_detection_recall | 0.75 | 3/4 seeded vague facts followed up; missed: ['F-SEC-02'] (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | conflict_detection_recall | 0.0 | 0/2 seeded conflicts found; 12 conflicts flagged; missed: ['C-REF-01', 'C-REF-02']; both sides reached the requirements for 2/2 (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | conflict_detection_precision | 0.0 | 0/2 seeded conflicts found; 12 conflicts flagged; missed: ['C-REF-01', 'C-REF-02']; both sides reached the requirements for 2/2 (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | control_coverage | 1.0 | 23/23 applicable controls |
| eval:refill_reminders:multi_agent | gold_control_coverage | 1.0 | 16/16 controls the gold requirements satisfy (gold not yet reviewed — provisional) |
| eval:refill_reminders:multi_agent | hallucination_rate | 0.014 | 147 citations checked |
| eval:refill_reminders:multi_agent | citation_correctness | 0.0 | share of 2 evidence quotes verbatim in the cited chunk |
| eval:refill_reminders:multi_agent | quality_first_draft | 0.809 | 29148 rule pass rate before clarification |
| eval:refill_reminders:multi_agent | quality_final | 0.871 | 29148 rule pass rate after clarification |
| eval:refill_reminders:multi_agent | traceability_coverage | 1.0 | requirements traceable to a stakeholder statement or corpus chunk |
| eval:refill_reminders:multi_agent | mean_confidence | 0.754 |  |
| eval:refill_reminders:multi_agent | escalated | 10 | requirements escalated for review |
| eval:refill_reminders:multi_agent | agent_calls_failed_after_repair | 6 | of 150 agent calls; ['extract.document-DOC-API-legacy-system-spec', 'extract.document-DOC-PROXY-policy', 'extract.document-DOC-REVIEWS-feedback', 'extract.document-DOC-SURVEY-questionnaire', 'extract.stakeholder-security-officer-SEC', 'stride'] |
| eval:refill_reminders:multi_agent | sdlc_recommendation | Agile | 62.5%; runner-up DevSecOps |
| eval:refill_reminders:multi_agent | sdlc_top1 |  | expert SDLC choice not yet recorded in gold.yaml |
| eval:refill_reminders:multi_agent | human_correction_rate |  | no human decisions recorded yet |
| eval:refill_reminders:multi_agent | processing_minutes | 65.9 | wall-clock, all steps |
| eval:refill_reminders:multi_agent | time_saved_vs_manual |  | manual effort not recorded in gold.yaml |
| eval:refill_reminders:multi_agent | injection_quarantined:INJ-REF-01 | 1 | the scanner quarantined the seeded injection before any agent saw it |
| eval:refill_reminders:baseline | precision | 0.222 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:refill_reminders:baseline | recall | 0.143 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:refill_reminders:baseline | f1 | 0.174 | automatic matches at cosine >= 0.6 (gold not yet reviewed — provisional) |
| eval:refill_reminders:baseline | requirements_generated | 18 | gold has 28 (gold not yet reviewed — provisional) |
| eval:refill_reminders:baseline | control_coverage | 0.391 | 9/23 applicable controls — upper bound: any cited chunk in the control's section counts |
| eval:refill_reminders:baseline | hallucination_rate | 0.2 | 20 citations checked |
| eval:refill_reminders:baseline | citation_correctness | 0.778 | share of 18 evidence quotes verbatim in the cited chunk |
| eval:refill_reminders:baseline | quality_final | 0.986 | 29148 rule pass rate (no clarification loop) |
| eval:refill_reminders:baseline | traceability_coverage | 1.0 | requirements citing a corpus chunk |
| eval:refill_reminders:baseline | ambiguity_detection_recall | 0.0 | no stakeholder interaction, by construction (gold not yet reviewed — provisional) |
| eval:refill_reminders:baseline | conflict_detection_recall | 0.0 | no conflict detection step, by construction (gold not yet reviewed — provisional) |
| eval:refill_reminders:baseline | processing_minutes | 6.5 | model time for the Part 1 calls |
| eval:refill_reminders:multi_agent | stakeholder_satisfaction_sus |  | no survey responses recorded |
| reproducibility | repeated_calls | 5 | identical calls (model, prompt, parameters) sent more than once |
| reproducibility | repeated_calls_identical | 4 | 4/5 returned byte-identical text |
| cost | llm_calls | 826 | {'smoke_test': 4, 'p1_requirements': 4, 'p1_repair': 4, 'p3_critic': 258, 'stakeholder_interaction.questions.PRES': 3, 'persona.answer': 66, 'stakeholder_interaction.followups.PRES': 3, 'stakeholder_interaction.questions.PHARM': 2, 'stakeholder_interaction.followups.PHARM': 2, 'stakeholder_interaction.questions.CSO': 1, 'stakeholder_interaction.followups.CSO': 1, 'stakeholder_interaction.questions.COMP': 2, 'stakeholder_interaction.followups.COMP': 2, 'stakeholder_interaction.questions.SEC': 3, 'stakeholder_interaction.followups.SEC': 3, 'stakeholder_interaction.questions.ARCH': 1, 'stakeholder_interaction.followups.ARCH': 1, 'stakeholder_interaction.questions.PO': 2, 'stakeholder_interaction.followups.PO': 2, 'extraction.extract.stakeholder-prescriber-PRES': 3, 'extraction.extract.stakeholder-prescriber-PRES.repair': 1, 'extraction.extract.stakeholder-pharmacist-PHARM': 2, 'extraction.extract.stakeholder-pharmacist-PHARM.repair': 1, 'extraction.extract.stakeholder-clinical-safety-officer-CSO': 1, 'extraction.extract.stakeholder-clinical-safety-officer-CSO.repair': 1, 'extraction.extract.stakeholder-compliance-officer-COMP': 2, 'extraction.extract.stakeholder-security-officer-SEC': 3, 'extraction.extract.stakeholder-security-officer-SEC.repair': 3, 'extraction.extract.stakeholder-architect-ARCH': 1, 'extraction.extract.stakeholder-architect-ARCH.repair': 1, 'extraction.extract.stakeholder-product-owner-PO': 2, 'extraction.extract.stakeholder-product-owner-PO.repair': 1, 'extraction.extract.document-DOC-KICKOFF-meeting-notes': 2, 'extraction.extract.document-DOC-KICKOFF-meeting-notes.repair': 2, 'extraction.extract.document-DOC-POLICY-policy': 1, 'extraction.extract.document-DOC-POLICY-policy.repair': 1, 'extraction.extract.document-DOC-EMAIL-email': 1, 'extraction.extract.document-DOC-EMAIL-email.repair': 1, 'extraction.extract.document-DOC-INTERFACE-legacy-system-spe': 1, 'extraction.extract.document-DOC-INTERFACE-legacy-system-spe.repair': 1, 'extraction.extract.document-DOC-INCIDENT-incident-report': 1, 'extraction.extract.document-DOC-INCIDENT-incident-report.repair': 1, 'classification.classify.1': 6, 'classification.classify.2': 6, 'classification.classify.3': 3, 'classification.classify.4': 3, 'classification.classify.5': 3, 'classification.classify.6': 3, 'classification.classify.7': 3, 'conflict_detection.pairs.1': 3, 'conflict_detection.pairs.2': 3, 'conflict_detection.pairs.3': 3, 'conflict_detection.pairs.4': 3, 'clarification.questions.r1.PRES': 3, 'clarification.questions.r1.PHARM': 2, 'clarification.questions.r1.COMP': 2, 'clarification.questions.r1.ARCH': 1, 'clarification.questions.r1.PO': 2, 'extraction.revise.FR-ERX-004': 1, 'extraction.revise.FR-ERX-005': 2, 'extraction.revise.NFR-ERX-002': 2, 'extraction.revise.FR-ERX-006': 2, 'extraction.revise.FR-ERX-007': 2, 'extraction.revise.NFR-ERX-003': 2, 'extraction.revise.FR-ERX-009': 1, 'extraction.revise.NFR-ERX-007': 2, 'extraction.revise.FR-ERX-015': 2, 'extraction.revise.FR-ERX-014': 2, 'extraction.revise.FR-ERX-018': 2, 'extraction.revise.FR-ERX-019': 2, 'extraction.revise.FR-ERX-020': 2, 'extraction.revise.FR-ERX-022': 1, 'extraction.revise.FR-ERX-023': 1, 'clarification.questions.r2.PRES': 3, 'clarification.questions.r2.PHARM': 2, 'clarification.questions.r2.COMP': 2, 'clarification.questions.r2.ARCH': 1, 'clarification.questions.r2.PO': 2, 'compliance.map.1': 3, 'compliance.map.2': 3, 'compliance.map.3': 3, 'compliance.map.4': 3, 'compliance.map.5': 3, 'compliance.map.6': 3, 'compliance.map.6.repair': 1, 'compliance.map.7': 3, 'compliance.map.8': 3, 'compliance.map.9': 3, 'compliance.gaps.1': 3, 'compliance.gaps.2': 3, 'security_privacy.stride': 3, 'security_privacy.stride.repair': 3, 'risk_analysis.risk.1': 3, 'risk_analysis.risk.2': 3, 'risk_analysis.risk.3': 3, 'risk_analysis.risk.4': 3, 'risk_analysis.risk.5': 3, 'risk_analysis.risk.6': 3, 'risk_analysis.risk.7': 3, 'risk_analysis.risk.8': 3, 'sdlc_selection.factors.primary': 3, 'sdlc_selection.factors.secondary': 3, 'sdlc_selection.explain': 3, 'sdlc_selection.tailor': 3, 'documentation.stories.1': 3, 'documentation.stories.2': 3, 'documentation.stories.2.repair': 1, 'documentation.stories.3': 3, 'documentation.stories.4': 3, 'documentation.use_cases': 3, 'stakeholder_interaction.questions.CRED': 1, 'stakeholder_interaction.followups.CRED': 1, 'stakeholder_interaction.questions.AUD': 1, 'stakeholder_interaction.followups.AUD': 1, 'extraction.extract.stakeholder-compliance-officer-CRED': 1, 'extraction.extract.stakeholder-auditor-AUD': 1, 'extraction.extract.document-DOC-CRED-policy': 1, 'extraction.extract.document-DOC-CRED-policy.repair': 1, 'extraction.extract.document-DOC-VENDOR-email': 1, 'extraction.extract.document-DOC-VENDOR-email.repair': 1, 'extraction.extract.document-DOC-FINDING-audit-finding': 1, 'extraction.extract.document-DOC-FINDING-audit-finding.repair': 1, 'extraction.extract.document-DOC-IDP-legacy-system-spec': 1, 'classification.classify.1.repair': 1, 'classification.classify.8': 2, 'classification.classify.9': 2, 'classification.classify.10': 1, 'classification.classify.11': 1, 'classification.classify.12': 1, 'classification.classify.13': 1, 'clarification.questions.r1.PRES.repair': 1, 'clarification.questions.r1.CRED': 1, 'clarification.questions.r1.SEC': 2, 'extraction.revise.FR-EPCS-001': 1, 'extraction.revise.NFR-EPCS-002': 2, 'extraction.revise.FR-EPCS-002': 2, 'extraction.revise.NFR-EPCS-003': 2, 'extraction.revise.FR-EPCS-003': 1, 'extraction.revise.FR-EPCS-004': 2, 'extraction.revise.NFR-EPCS-007': 1, 'extraction.revise.FR-EPCS-015': 2, 'extraction.revise.NFR-EPCS-043': 2, 'extraction.revise.NFR-EPCS-044': 2, 'extraction.revise.FR-EPCS-016': 2, 'extraction.revise.NFR-EPCS-046': 2, 'extraction.revise.NFR-EPCS-048': 2, 'extraction.revise.FR-EPCS-018': 2, 'extraction.revise.FR-EPCS-019': 2, 'extraction.revise.FR-EPCS-020': 2, 'extraction.revise.FR-EPCS-021': 2, 'extraction.revise.FR-EPCS-024': 2, 'extraction.revise.NFR-EPCS-010': 2, 'extraction.revise.NFR-EPCS-011': 2, 'extraction.revise.FR-EPCS-007': 2, 'extraction.revise.FR-EPCS-008': 2, 'extraction.revise.NFR-EPCS-016': 2, 'extraction.revise.FR-EPCS-009': 2, 'extraction.revise.NFR-EPCS-019': 2, 'extraction.revise.NFR-EPCS-019.repair': 1, 'extraction.revise.NFR-EPCS-021': 2, 'extraction.revise.NFR-EPCS-022': 2, 'extraction.revise.NFR-EPCS-023': 2, 'extraction.revise.NFR-EPCS-024': 1, 'extraction.revise.NFR-EPCS-025': 2, 'extraction.revise.FR-EPCS-013': 2, 'extraction.revise.NFR-EPCS-029': 1, 'extraction.revise.NFR-EPCS-030': 2, 'extraction.revise.NFR-EPCS-031': 1, 'extraction.revise.FR-EPCS-014': 2, 'extraction.revise.NFR-EPCS-032': 1, 'extraction.revise.NFR-EPCS-033': 1, 'extraction.revise.NFR-EPCS-034': 1, 'clarification.questions.r2.PRES.repair': 1, 'clarification.questions.r2.CRED': 1, 'clarification.questions.r2.SEC': 2, 'compliance.map.1.repair': 1, 'compliance.map.4.repair': 1, 'compliance.map.10': 2, 'compliance.map.11': 2, 'compliance.map.12': 2, 'compliance.map.12.repair': 1, 'compliance.map.13': 2, 'compliance.map.14': 1, 'compliance.map.15': 1, 'compliance.map.15.repair': 1, 'compliance.map.16': 1, 'compliance.map.17': 1, 'compliance.map.17.repair': 1, 'compliance.map.18': 1, 'compliance.map.19': 1, 'compliance.map.19.repair': 1, 'risk_analysis.risk.9': 2, 'risk_analysis.risk.10': 2, 'risk_analysis.risk.11': 2, 'risk_analysis.risk.12': 1, 'risk_analysis.risk.13': 1, 'risk_analysis.risk.14': 1, 'sdlc_selection.factors.primary.repair': 1, 'sdlc_selection.factors.secondary.repair': 2, 'documentation.stories.5': 2, 'stakeholder_interaction.questions.PAT': 1, 'stakeholder_interaction.followups.PAT': 1, 'stakeholder_interaction.questions.CARE': 1, 'stakeholder_interaction.followups.CARE': 1, 'extraction.extract.stakeholder-patient-PAT': 1, 'extraction.extract.stakeholder-patient-CARE': 1, 'extraction.extract.stakeholder-patient-CARE.repair': 1, 'extraction.extract.document-DOC-SURVEY-questionnaire': 1, 'extraction.extract.document-DOC-SURVEY-questionnaire.repair': 1, 'extraction.extract.document-DOC-REVIEWS-feedback': 1, 'extraction.extract.document-DOC-REVIEWS-feedback.repair': 1, 'extraction.extract.document-DOC-API-legacy-system-spec': 1, 'extraction.extract.document-DOC-API-legacy-system-spec.repair': 1, 'extraction.extract.document-DOC-PROXY-policy': 1, 'extraction.extract.document-DOC-PROXY-policy.repair': 1, 'clarification.questions.r1.PAT': 1, 'clarification.questions.r1.CARE': 1, 'extraction.revise.FR-REF-002': 1, 'extraction.revise.FR-REF-003': 2, 'extraction.revise.FR-REF-004': 1, 'extraction.revise.FR-REF-005': 2, 'extraction.revise.FR-REF-006': 2, 'extraction.revise.NFR-REF-001': 2, 'extraction.revise.NFR-REF-002': 2, 'extraction.revise.FR-REF-009': 2, 'extraction.revise.FR-REF-010': 2, 'extraction.revise.FR-REF-011': 2, 'extraction.revise.FR-REF-012': 2, 'extraction.revise.NFR-REF-003': 2, 'extraction.revise.FR-REF-014': 2, 'extraction.revise.FR-REF-015': 1, 'extraction.revise.FR-REF-016': 1, 'extraction.revise.FR-REF-017': 2, 'extraction.revise.NFR-REF-004': 1, 'extraction.revise.FR-REF-030': 1, 'extraction.revise.FR-REF-031': 2, 'extraction.revise.FR-REF-032': 2, 'extraction.revise.FR-REF-034': 1, 'extraction.revise.FR-REF-035': 2, 'extraction.revise.FR-REF-036': 1, 'extraction.revise.FR-REF-037': 2, 'extraction.revise.FR-REF-039': 2, 'extraction.revise.FR-REF-040': 2, 'extraction.revise.FR-REF-041': 2, 'extraction.revise.FR-REF-044': 1, 'extraction.revise.FR-REF-045': 2, 'extraction.revise.NFR-REF-007': 2, 'extraction.revise.FR-REF-019': 1, 'extraction.revise.FR-REF-020': 2, 'extraction.revise.FR-REF-021': 2, 'extraction.revise.FR-REF-022': 2, 'extraction.revise.FR-REF-025': 2, 'extraction.revise.FR-REF-026': 2, 'extraction.revise.FR-REF-027': 2, 'extraction.revise.FR-REF-028': 2, 'clarification.questions.r2.PAT': 1, 'clarification.questions.r2.CARE': 1, 'compliance.map.5.repair': 1, 'compliance.map.10.repair': 1, 'risk_analysis.risk.6.repair': 1, 'risk_analysis.risk.11.repair': 1, 'documentation.stories.6': 1, 'documentation.stories.7': 1, 'documentation.stories.8': 1, 'p2_sdlc': 18, 'extraction.extract.document-DOC-VENDOR': 1, 'extraction.extract.document-DOC-VENDOR.repair': 1, 'injection_replay.undefended': 3, 'extraction.extract.document-DOC-EMAIL': 1, 'extraction.extract.document-DOC-EMAIL.repair': 1, 'extraction.extract.document-DOC-REVIEWS': 1, 'extraction.extract.document-DOC-REVIEWS.repair': 1} |
| cost | llm_call_errors | 0 | failed attempts (retried) |
| cost | prompt_tokens_total | 1021425 |  |
| cost | completion_tokens_total | 399570 |  |
| cost | tokens_total | 1420995 |  |
| cost | wall_clock_s | 17778.2 | 296.3 minutes of model time |

## Hallucination audit

| req_id | cited_entity | entity_type | verdict | severity |
|---|---|---|---|---|
| FR-01 | This resource covers all type of orders for medications for a patient. This includes inpatient medication orders as well as community orders (whether filled by  | evidence_quote | verified | none |
| FR-02 | Before a medication order is completed and acted upon during computerized provider order entry (CPOE), interventions must automatically indicate to a user drug- | evidence_quote | verified | none |
| FR-03 | The electronic prescription application must require the individual practitioner to complete a two-factor authentication protocol as specified in § 1311.140(a)( | evidence_quote | verified | none |
| FR-04 | An electronic prescription must be transmitted from the practitioner to the pharmacy in its electronic form. At no time may an intermediary convert an electroni | evidence_quote | verified | none |
| FR-05 | The application provider must establish and implement a list of auditable events. Auditable events must, at a minimum, include the following: (1) Attempted unau | evidence_quote | verified | none |
| FR-06 | The pharmacy application must protect the stored audit records from unauthorized deletion. The pharmacy application shall prevent modifications to the audit rec | evidence_quote | misattributed | medium |
| FR-07 | Records required by this part must be maintained electronically for two years from the date of their creation or receipt. | evidence_quote | fabricated | high |
| FR-08 | These instances can be linked in different ways, depending on the needs of the workflow. For guidance, refer to the Request pattern | evidence_quote | verified | none |
| FR-09 | Enable a user to record, change, and access patient demographic and observations data including race, ethnicity, preferred language, sex, sex parameter for clin | evidence_quote | verified | none |
| FR-11 | Any change to the content during transmission, including truncation or removal of data, will render the electronic prescription invalid. | evidence_quote | verified | none |
| FR-12 | An electronic prescription must be transmitted from the practitioner to the pharmacy in its electronic form. At no time may an intermediary convert an electroni | evidence_quote | verified | none |
| FR-13 | The electronic prescription application must not allow the transmission of an electronic prescription if an original prescription was printed prior to attempted | evidence_quote | verified | none |
| FR-14 | The electronic prescription application must transmit the electronic prescription as soon as possible after signature by the practitioner. | evidence_quote | verified | none |
| FR-15 | The electronic prescription application may print a prescription that has been transmitted only if an intermediary or the designated pharmacy notifies a practit | evidence_quote | verified | none |
| FR-16 | The electronic prescription data may be converted from one software version to another between the electronic prescription application and the pharmacy applicat | evidence_quote | verified | none |
| FR-17 | The electronic prescription application must transmit the electronic prescription as soon as possible after signature by the practitioner. | evidence_quote | verified | none |
| FR-18 | The electronic prescription application must transmit the electronic prescription as soon as possible after signature by the practitioner. | evidence_quote | verified | none |

## SDLC runs

| run_id | model | framing | trial | recommended_sdlc | recommended_canonical |
|---|---|---|---|---|---|
| R1 | primary | neutral | 1 | Agile/Scrum | Agile |
| R1 | primary | neutral | 2 | Agile/Scrum | Agile |
| R1 | primary | neutral | 3 | Agile/Scrum | Agile |
| R1 | secondary | neutral | 1 | Agile/Scrum | Agile |
| R1 | secondary | neutral | 2 | Agile/Scrum | Agile |
| R1 | secondary | neutral | 3 | Agile/Scrum | Agile |
| R2 | primary | agile_primed | 1 | Agile/Scrum | Agile |
| R2 | primary | agile_primed | 2 | Agile/Scrum | Agile |
| R2 | primary | agile_primed | 3 | Agile/Scrum | Agile |
| R2 | secondary | agile_primed | 1 | Agile/Scrum | Agile |
| R2 | secondary | agile_primed | 2 | Agile/Scrum | Agile |
| R2 | secondary | agile_primed | 3 | Agile/Scrum | Agile |
| R3 | primary | plan_primed | 1 | Waterfall | Waterfall |
| R3 | primary | plan_primed | 2 | Waterfall | Waterfall |
| R3 | primary | plan_primed | 3 | Waterfall | Waterfall |
| R3 | secondary | plan_primed | 1 | V-Model | V-Model |
| R3 | secondary | plan_primed | 2 | V-Model | V-Model |
| R3 | secondary | plan_primed | 3 | V-Model | V-Model |

## SDLC engine consistency (does each run's pick follow from its own scores?)

| run_id | model | framing | trial | llm_recommendation | engine_top | engine_top_pct | consistent |
|---|---|---|---|---|---|---|---|
| R1 | primary | neutral | 1 | Agile | V-Model | 85.0 | False |
| R1 | primary | neutral | 2 | Agile | V-Model | 70.0 | False |
| R1 | primary | neutral | 3 | Agile | V-Model | 80.0 | False |
| R1 | secondary | neutral | 1 | Agile | V-Model | 90.0 | False |
| R1 | secondary | neutral | 2 | Agile | V-Model | 85.0 | False |
| R1 | secondary | neutral | 3 | Agile | V-Model | 90.0 | False |
| R2 | primary | agile_primed | 1 | Agile | DevSecOps | 66.7 | False |
| R2 | primary | agile_primed | 2 | Agile | V-Model | 55.0 | False |
| R2 | primary | agile_primed | 3 | Agile | Agile | 58.3 | True |
| R2 | secondary | agile_primed | 1 | Agile | DevSecOps | 75.0 | False |
| R2 | secondary | agile_primed | 2 | Agile | DevSecOps | 75.0 | False |
| R2 | secondary | agile_primed | 3 | Agile | Hybrid | 81.2 | False |
| R3 | primary | plan_primed | 1 | Waterfall | V-Model | 90.0 | False |
| R3 | primary | plan_primed | 2 | Waterfall | V-Model | 90.0 | False |
| R3 | primary | plan_primed | 3 | Waterfall | V-Model | 90.0 | False |
| R3 | secondary | plan_primed | 1 | V-Model | Waterfall | 91.7 | False |
| R3 | secondary | plan_primed | 2 | V-Model | Waterfall | 95.8 | False |
| R3 | secondary | plan_primed | 3 | V-Model | Waterfall | 91.7 | False |

## 29148 pass rate by attribute

| attribute | rule_pass | llm_pass |
|---|---|---|
| complete | 1.0 | 1.0 |
| conforming | 1.0 | 1.0 |
| feasible | 1.0 | 1.0 |
| necessary | 1.0 | 1.0 |
| singular | 1.0 | 1.0 |
| traceable | 1.0 | 1.0 |
| unambiguous | 1.0 | 0.0 |
| verifiable | 0.67 | 0.0 |

## Scorer disagreements (adjudication candidates)

| req_id | attribute | rule_score | llm_score | note |
|---|---|---|---|---|
| FR-01 | unambiguous | 1 | 0 | rule: no weak terms matched \|\| llm: The phrase 'successfully create and submit an e-Rx' is vague and could be interpreted in multiple ways. |
| FR-02 | unambiguous | 1 | 0 | rule: no weak terms matched \|\| llm: The phrase 'real-time' is vague without a specific timeframe or threshold. |
| FR-03 | unambiguous | 1 | 0 | rule: no weak terms matched \|\| llm: The phrase 'two-factor authentication protocol' is vague and could refer to different protocols. |
| FR-03 | verifiable | 1 | 0 | rule: observable pass/fail condition present \|\| llm: The acceptance criteria do not specify what constitutes a 'two-factor authentication protocol', making it unverifiable. |
| FR-04 | unambiguous | 1 | 0 | rule: no weak terms matched \|\| llm: The phrase 'without the digital signature' is ambiguous and could be interpreted in multiple ways. |
| FR-04 | verifiable | 1 | 0 | rule: observable pass/fail condition present \|\| llm: The acceptance criteria 'The system can transmit a controlled-substance prescription to a pharmacy in its electronic form' are not observable or testable without specifying the exact conditions under which the transmission should occur. |
| FR-05 | unambiguous | 1 | 0 | rule: no weak terms matched \|\| llm: The phrase 'and the outcome of the event' is vague and could be interpreted in multiple ways. |
| FR-05 | verifiable | 1 | 0 | rule: observable pass/fail condition present \|\| llm: The acceptance criteria include 'the outcome of the event', which is not clearly defined and thus not verifiable. |
| FR-06 | unambiguous | 1 | 0 | rule: no weak terms matched \|\| llm: The phrase 'protects them from unauthorized deletion' is vague and could be interpreted in multiple ways. |
| FR-06 | verifiable | 1 | 0 | rule: observable pass/fail condition present \|\| llm: The acceptance criteria 'The system prevents modifications to the audit records and protects them from unauthorized deletion' are not observable or testable as written. |
| FR-07 | unambiguous | 1 | 0 | rule: no weak terms matched \|\| llm: The phrase 'at least two years' is vague and could be misinterpreted. It should specify a precise duration. |
| FR-07 | verifiable | 1 | 0 | rule: observable pass/fail condition present \|\| llm: The acceptance criteria 'The system maintains and retains all archived records electronically for a minimum period of two years from the date of their receipt or creation' are not observable. A specific test method or metric is needed to verify compliance. |

## Case-study evaluation (multi-agent vs baseline)

| case | metric | baseline | multi_agent |
|---|---|---|---|
| epcs_signing | agent_calls_failed_after_repair |  | 12 |
| epcs_signing | ambiguity_detection_recall | 0.0 | 0.833 |
| epcs_signing | category_agreement |  | 0.366 |
| epcs_signing | citation_correctness | 1.0 | 0.73 |
| epcs_signing | conflict_detection_precision |  | 0.0 |
| epcs_signing | conflict_detection_recall | 0.0 | 0.0 |
| epcs_signing | control_coverage | 0.485 | 1.0 |
| epcs_signing | escalated |  | 22 |
| epcs_signing | f1 | 0.415 | 0.525 |
| epcs_signing | gold_control_coverage |  | 1.0 |
| epcs_signing | hallucination_rate | 0.0 | 0.054 |
| epcs_signing | injection_quarantined:INJ-EPCS-01 |  | 1 |
| epcs_signing | mean_confidence |  | 0.73 |
| epcs_signing | precision | 0.611 | 0.373 |
| epcs_signing | precision_elicited |  | 0.419 |
| epcs_signing | processing_minutes | 5.7 | 93.7 |
| epcs_signing | quality_final | 0.944 | 0.905 |
| epcs_signing | quality_first_draft |  | 0.895 |
| epcs_signing | recall | 0.314 | 0.886 |
| epcs_signing | requirements_generated | 18.0 | 83 |
| epcs_signing | sdlc_recommendation |  | Waterfall |
| epcs_signing | traceability_coverage | 1.0 | 1.0 |
| erx_issuance | agent_calls_failed_after_repair |  | 11 |
| erx_issuance | ambiguity_detection_recall | 0.0 | 0.857 |
| erx_issuance | category_agreement |  | 0.506 |
| erx_issuance | citation_correctness | 0.688 | 0.625 |
| erx_issuance | conflict_detection_precision |  | 0.0 |
| erx_issuance | conflict_detection_recall | 0.0 | 0.0 |
| erx_issuance | control_coverage | 0.357 | 1.0 |
| erx_issuance | escalated |  | 9 |
| erx_issuance | f1 | 0.164 | 0.636 |
| erx_issuance | gold_control_coverage |  | 1.0 |
| erx_issuance | hallucination_rate | 0.312 | 0.029 |
| erx_issuance | mean_confidence |  | 0.745 |
| erx_issuance | precision | 0.312 | 0.651 |
| erx_issuance | precision_elicited |  | 0.778 |
| erx_issuance | processing_minutes | 6.2 | 68.8 |
| erx_issuance | quality_final | 0.953 | 0.942 |
| erx_issuance | quality_first_draft |  | 0.924 |
| erx_issuance | recall | 0.111 | 0.622 |
| erx_issuance | requirements_generated | 16.0 | 43 |
| erx_issuance | sdlc_recommendation |  | Waterfall |
| erx_issuance | traceability_coverage | 1.0 | 1.0 |
| erx_issuance | injection_quarantined:INJ-ERX-01 |  | 1 |
| refill_reminders | agent_calls_failed_after_repair |  | 6 |
| refill_reminders | ambiguity_detection_recall | 0.0 | 0.75 |
| refill_reminders | category_agreement |  | 0.509 |
| refill_reminders | citation_correctness | 0.778 | 0.0 |
| refill_reminders | conflict_detection_precision |  | 0.0 |
| refill_reminders | conflict_detection_recall | 0.0 | 0.0 |
| refill_reminders | control_coverage | 0.391 | 1.0 |
| refill_reminders | escalated |  | 10 |
| refill_reminders | f1 | 0.174 | 0.4 |
| refill_reminders | gold_control_coverage |  | 1.0 |
| refill_reminders | hallucination_rate | 0.2 | 0.014 |
| refill_reminders | mean_confidence |  | 0.754 |
| refill_reminders | precision | 0.222 | 0.29 |
| refill_reminders | precision_elicited |  | 0.353 |
| refill_reminders | processing_minutes | 6.5 | 65.9 |
| refill_reminders | quality_final | 0.986 | 0.871 |
| refill_reminders | quality_first_draft |  | 0.809 |
| refill_reminders | recall | 0.143 | 0.643 |
| refill_reminders | requirements_generated | 18.0 | 62 |
| refill_reminders | sdlc_recommendation |  | Agile |
| refill_reminders | traceability_coverage | 1.0 | 1.0 |
| refill_reminders | injection_quarantined:INJ-REF-01 |  | 1 |

## SDLC ranking — epcs_signing

| model | suitability_pct | supporting_rules |
|---|---|---|
| Waterfall | 87.5 | R-WF |
| V-Model | 85.0 | R-V |
| Hybrid | 75.0 | - |
| Spiral | 52.5 | - |
| DevSecOps | 37.5 | - |
| Agile | 25.0 | - |

Escalated: near tie: Waterfall 87.5% vs V-Model 85.0%; the two models disagree by 2+ points on: system_size, stakeholder_availability

## SDLC ranking — erx_issuance

| model | suitability_pct | supporting_rules |
|---|---|---|
| Waterfall | 79.2 | R-WF |
| V-Model | 75.0 | R-V |
| Hybrid | 65.6 | - |
| Spiral | 57.5 | - |
| DevSecOps | 54.2 | - |
| Agile | 35.4 | - |

Escalated: near tie: Waterfall 79.2% vs V-Model 75.0%; the two models disagree by 2+ points on: system_size, legacy_dependence, change_frequency, continuous_delivery_need, stakeholder_availability

## SDLC ranking — refill_reminders

| model | suitability_pct | supporting_rules |
|---|---|---|
| Agile | 62.5 | - |
| DevSecOps | 62.5 | - |
| Hybrid | 43.8 | - |
| Waterfall | 39.6 | - |
| Spiral | 37.5 | - |
| V-Model | 32.5 | - |

Escalated: no brief rule supports the top-ranked model (Agile); near tie: Agile 62.5% vs DevSecOps 62.5%; the two models disagree by 2+ points on: regulatory_criticality, continuous_delivery_need, stakeholder_availability, formal_verification_need, failure_consequence

## 29148 rule pass rate by attribute — epcs_signing

| attribute | multi_agent_first_draft | multi_agent_final | baseline |
|---|---|---|---|
| complete | 1.0 | 1.0 | 1.0 |
| conforming | 1.0 | 0.723 | 1.0 |
| feasible | 1.0 | 1.0 | 1.0 |
| necessary | 0.851 | 0.94 | 1.0 |
| singular | 0.959 | 0.94 | 0.944 |
| traceable | 0.973 | 0.976 | 1.0 |
| unambiguous | 0.797 | 0.94 | 0.889 |
| verifiable | 0.581 | 0.723 | 0.722 |

## 29148 rule pass rate by attribute — erx_issuance

| attribute | multi_agent_first_draft | multi_agent_final | baseline |
|---|---|---|---|
| complete | 1.0 | 1.0 | 1.0 |
| conforming | 1.0 | 0.93 | 1.0 |
| feasible | 1.0 | 1.0 | 1.0 |
| necessary | 1.0 | 1.0 | 1.0 |
| singular | 0.889 | 0.837 | 1.0 |
| traceable | 1.0 | 1.0 | 1.0 |
| unambiguous | 0.75 | 0.93 | 0.875 |
| verifiable | 0.75 | 0.837 | 0.75 |

## 29148 rule pass rate by attribute — refill_reminders

| attribute | multi_agent_first_draft | multi_agent_final | baseline |
|---|---|---|---|
| complete | 1.0 | 1.0 | 1.0 |
| conforming | 1.0 | 0.871 | 1.0 |
| feasible | 1.0 | 1.0 | 1.0 |
| necessary | 0.333 | 0.581 | 1.0 |
| singular | 1.0 | 1.0 | 1.0 |
| traceable | 1.0 | 1.0 | 1.0 |
| unambiguous | 0.882 | 0.919 | 1.0 |
| verifiable | 0.255 | 0.597 | 0.889 |

## Case registers

| case | register | counts |
|---|---|---|
| epcs_signing | approval items | 300: requirement_baseline 83, regulatory_interpretation 80, clinical_safety 60, security_requirement 46, conflict 15, architecture_critical 7, sdlc_selection 4, production_readiness 4, injection_quarantine 1 |
| epcs_signing | approval priority | 300: normal 189, high 111 |
| epcs_signing | security events | 2: prompt_injection 1, phi_masked 1 |
| epcs_signing | open issues | 150: conflict 45, untestable 23, nonconforming 23, low_confidence 22, undefined_term 12, non_singular 5, ambiguity 5, duplicate 5, unmitigated_threat 5, missing_source 2, missing_control 1, security:prompt_injection 1, security:phi_masked 1 |
| epcs_signing | risk levels | 83: Critical 39, High 30, Medium 14 |
| epcs_signing | threats | 8: unmitigated 5 |
| erx_issuance | approval items | 157: requirement_baseline 43, regulatory_interpretation 42, clinical_safety 22, security_requirement 18, architecture_critical 16, conflict 5, sdlc_selection 4, production_readiness 4, injection_quarantine 3 |
| erx_issuance | approval priority | 157: normal 107, high 50 |
| erx_issuance | security events | 4: prompt_injection 3, phi_masked 1 |
| erx_issuance | open issues | 47: conflict 12, low_confidence 9, untestable 7, non_singular 7, ambiguity 3, nonconforming 3, security:prompt_injection 3, undefined_term 2, security:phi_masked 1 |
| erx_issuance | risk levels | 43: Critical 18, High 13, Medium 12 |
| erx_issuance | threats | 8: unmitigated 0 |
| refill_reminders | approval items | 188: requirement_baseline 62, regulatory_interpretation 60, clinical_safety 23, security_requirement 19, conflict 12, sdlc_selection 4, production_readiness 4, architecture_critical 2, injection_quarantine 2 |
| refill_reminders | approval priority | 188: normal 126, high 62 |
| refill_reminders | security events | 3: prompt_injection 2, suspicious_link 1 |
| refill_reminders | open issues | 111: conflict 27, duplicate 26, untestable 25, low_confidence 10, nonconforming 8, undefined_term 7, ambiguity 5, security:prompt_injection 2, security:suspicious_link 1 |
| refill_reminders | risk levels | 62: High 31, Critical 20, Medium 11 |
| refill_reminders | threats | 8: unmitigated 0 |
