# BUILD.md — SE Individual Project: LLM-Assisted Requirements Engineering & SDLC Selection

> Spec for Claude Code. Build this repo end-to-end. Do not skip the validation layer — it is the graded differentiator.

---

## 0. Project Summary

Two-part academic deliverable for a Software Engineering course.

**Part 1 (RE):** Ground a lightweight local LLM on real healthcare requirement documents. Prompt it to generate requirements for one specific functionality, with per-requirement reasoning and source traceability.

**Part 2 (SDLC):** Feed the generated requirement set back into the LLM. Ask it to select the most appropriate SDLC model with a defensible software-engineering justification. Stress-test the answer for reflex bias.

**Grading reality:** the LLM is the instrument, not the contribution. The contribution is the RE methodology, the traceability, and the ISO/IEC/IEEE 29148 quality audit of the LLM's output.

**Chosen functionality (default):** Electronic Prescription (e-Rx) issuance with drug–drug interaction checking and controlled-substance handling.
Rationale: dense NFR surface (safety, auditability, consent, latency, regulatory), unlike a CRUD feature like "patient login".

---

## 1. Tech Stack & Constraints

| Concern | Choice | Notes |
|---|---|---|
| Runtime | Python 3.11+ | Windows-friendly, no WSL requirement |
| LLM host | Ollama (local) | Must be demonstrably local — screenshot `ollama list` for report |
| Primary model | `qwen2.5:7b-instruct` | Fallback: `phi4-mini`, `llama3.1:8b` |
| Secondary model | one alternate from above | Needed for cross-model agreement analysis |
| Retrieval | `sentence-transformers` (all-MiniLM-L6-v2) + FAISS | Keep it simple; flat L2 index is fine at this corpus size |
| Parsing | `pypdf`, `beautifulsoup4` | |
| Data | `pandas` | CSV is the interchange format throughout |
| Env | `venv` + `requirements.txt` | No Docker needed |
| Determinism | `temperature=0.1`, fixed `seed`, log every param | Reproducibility is a rubric item |

**Hard constraints**

- No hosted frontier APIs anywhere in the pipeline. Local only.
- Every LLM call logs: model, params, full prompt, raw response, timestamp, wall-clock latency.
- Never hand-edit generated artifacts. Raw output is evidence. Corrections go in a separate reviewed file with a diff.

---

## 2. Repository Layout

```
se-llm-requirements/
├── README.md
├── BUILD.md
├── requirements.txt
├── .env.example
├── config/
│   ├── models.yaml            # model ids, temp, seed, ctx window
│   └── pipeline.yaml          # paths, chunk size, top-k, target functionality
├── corpus/
│   ├── raw/                   # unmodified source docs (PDF/HTML/MD)
│   ├── processed/             # cleaned .txt, one per source
│   └── MANIFEST.csv           # provenance table (see §3)
├── src/
│   ├── __init__.py
│   ├── ingest.py              # raw -> processed -> chunks
│   ├── index.py               # build/load FAISS index
│   ├── llm.py                 # Ollama client wrapper + logging + retries
│   ├── generate_reqs.py       # PART 1 driver
│   ├── select_sdlc.py         # PART 2 driver
│   ├── validate.py            # 29148 quality audit + hallucination check
│   ├── metrics.py             # agreement, coverage, stability scores
│   └── report.py              # assembles figures + tables for the writeup
├── prompts/
│   ├── p1_requirements.txt
│   ├── p1_repair.txt          # schema-violation retry prompt
│   ├── p2_sdlc_neutral.txt
│   ├── p2_sdlc_agile_primed.txt
│   ├── p2_sdlc_plan_primed.txt
│   └── p3_critic.txt          # LLM-as-critic for validation cross-check
├── outputs/
│   ├── requirements.csv
│   ├── requirements_reasoning.csv
│   ├── traceability_matrix.csv
│   ├── sdlc_analysis.csv
│   ├── validation_29148.csv
│   ├── hallucination_audit.csv
│   └── metrics_summary.csv
├── logs/
│   └── llm_calls.jsonl
├── figures/
└── report/
    └── report.md              # final writeup skeleton
```

---

## 3. Corpus (Part 1 input)

Target **4–6 documents**. Prefer openly licensed sources. Record everything in `corpus/MANIFEST.csv`:

```
doc_id, title, source_url, publisher, year, license, doc_type, pages, sha256, retrieved_on
```

Shortlist (verify each is fetchable before committing to it):

- IEEE 830 / ISO-IEC-IEEE 29148 sample SRS (structure exemplar)
- OpenMRS or OpenEMR functional requirement / design docs
- HL7 FHIR R4 resource specs — `MedicationRequest`, `Patient`, `AllergyIntolerance`, `Provenance`
- HIPAA Security Rule 45 CFR §164.312 (technical safeguards)
- ONC 2015 Edition certification criteria — e-prescribing, CPOE, audit log
- A published EHR/HIS SRS from an academic or government source

`doc_id` scheme: `D01`…`D06`. These IDs propagate into every citation the LLM produces — that is the backbone of traceability.

### Ingestion rules

- Strip headers/footers/page numbers, normalise whitespace, keep section headings — headings become chunk metadata.
- Chunk at **~800 tokens, 120 overlap**, split on heading boundaries where possible.
- Chunk id: `D03#S4.2#c07`. Store `{chunk_id, doc_id, section, text, token_count}`.

---

## 4. Part 1 — Requirement Generation

### Pipeline

1. Load index, retrieve **top-12** chunks for the target functionality (query = functionality description + expanded keyword set).
2. Build prompt from `prompts/p1_requirements.txt` with retrieved chunks injected, each labelled with its `chunk_id`.
3. Call model, temperature 0.1, request strict JSON.
4. Validate against schema. On failure, one repair attempt via `p1_repair.txt`, then hard-fail loudly.
5. Emit CSVs.

### `outputs/requirements.csv` schema

| column | type | notes |
|---|---|---|
| req_id | str | `FR-01`, `NFR-01` |
| type | enum | FR \| NFR |
| nfr_category | enum | security, performance, reliability, usability, compliance, maintainability, portability, — |
| statement | str | Single "shall" sentence. One requirement per row, no conjunctions |
| actor | str | prescriber, pharmacist, patient, system, auditor |
| priority | enum | Must \| Should \| Could \| Won't |
| verification_method | enum | Test \| Demonstration \| Inspection \| Analysis |
| acceptance_criteria | str | Observable pass/fail condition |
| risk_class | enum | Safety-critical \| Business-critical \| Standard |
| volatility | enum | High \| Medium \| Low (drives Part 2) |
| source_chunk_ids | str | semicolon-separated, e.g. `D02#S3.1#c02;D04#S1#c11` |
| derived | bool | true = inferred, not stated in corpus |

### `outputs/requirements_reasoning.csv`

`req_id, reasoning, evidence_quote, inference_type`

where `inference_type ∈ {direct_extraction, generalization, domain_inference, regulatory_derivation}`.

**Per-requirement reasoning, not one summary blob.** A single trailing rationale paragraph is unusable in a viva and unusable for traceability.

### Targets

- 18–25 requirements, at least 8 NFRs.
- ≥70% must cite at least one real `chunk_id`.
- Zero rows with `source_chunk_ids` empty and `derived=false` — that combination is an integrity bug.

### `outputs/traceability_matrix.csv`

Requirements × source docs. Cells: `D` direct, `I` inferred, blank. Render as a heatmap into `figures/`. Compute per-document coverage — an uncited source document is itself a finding worth reporting.

---

## 5. Part 2 — SDLC Selection

Feed **only** `requirements.csv` (statements + type + risk_class + volatility + priority). Withhold the reasoning file so the model reasons from the artifact, not from its own prior narrative.

### Three runs, three framings

| run_id | prompt | purpose |
|---|---|---|
| R1 | `p2_sdlc_neutral.txt` | baseline |
| R2 | `p2_sdlc_agile_primed.txt` | "the team is small and co-located, moving fast" |
| R3 | `p2_sdlc_plan_primed.txt` | "the client is a regulated hospital network with a fixed audit date" |

Repeat each run **3×** and across **2 models** → 18 data points.

### Decision criteria the model must score (1–5, with justification per criterion)

requirement volatility · regulatory/audit burden · safety criticality · cost of late defect · user/domain-expert availability · team size & distribution · schedule rigidity · integration complexity with legacy systems

### `outputs/sdlc_analysis.csv`

`run_id, model, framing, trial, recommended_sdlc, runner_up, criterion, score, criterion_justification, cited_req_ids`

### Analysis to write up

- **Stability:** does the recommendation flip under framing? Report a mode + flip rate.
- **Cross-model agreement:** simple percent agreement on top choice.
- **Grounding:** fraction of justifications citing specific `req_id`s vs generic SE platitudes. This is the strongest signal of reasoning vs pattern-matching.
- **Expected finding to interrogate, not accept:** models default to "Agile/Scrum" by reflex. For a safety-critical, heavily regulated, low-volatility requirement set, defensible answers include V-Model, Spiral, or a hybrid (iterative delivery inside a V-shaped verification and compliance wrapper). Your report should argue the correct answer independently and then assess whether the LLM got there and *why*.

---

## 6. Validation Layer (the graded differentiator)

### 6.1 ISO/IEC/IEEE 29148 quality audit

Score every requirement 0/1 on: **necessary, unambiguous, complete, singular, feasible, verifiable, conforming, traceable**.

Two independent scorers:

1. Rule-based (`validate.py`) — regex/heuristics for weak words (`fast`, `user-friendly`, `efficient`, `appropriate`, `as needed`), missing "shall", conjunctions implying compound requirements, absent acceptance criteria, empty traceability.
2. LLM-as-critic (`p3_critic.txt`) on a fresh context.

Emit both, report agreement rate, manually adjudicate disagreements in a column `human_adjudication`. Manual adjudication of ~10 conflicts is enough and it demonstrates method.

`outputs/validation_29148.csv`:
`req_id, attribute, rule_score, llm_score, agreement, human_adjudication, note`

### 6.2 Hallucination audit

For every regulatory or standards citation the LLM produced (CFR sections, HL7 resource names, ONC criteria, IEEE clauses), verify it exists in the corpus or in the actual standard.

`outputs/hallucination_audit.csv`:
`req_id, cited_entity, entity_type, verdict, evidence, severity`

`verdict ∈ {verified, unverifiable, fabricated, misattributed}`

Fabricated regulatory citations in a healthcare context are a safety argument, not a nitpick. Lead the discussion section with this.

### 6.3 Metrics summary

Requirement count by type · 29148 pass rate per attribute · traceability coverage · hallucination rate · SDLC flip rate · cross-model agreement · total tokens and wall-clock.

---

## 7. Build Order

1. Scaffold repo, `requirements.txt`, config files, `.env.example`.
2. `llm.py` — Ollama wrapper with JSONL logging, retry, param capture. Smoke-test it first; nothing else works if this is flaky.
3. `ingest.py` + `MANIFEST.csv`. Verify chunk counts and that `chunk_id` round-trips.
4. `index.py` — build FAISS, sanity-check retrieval quality manually on 3 queries before proceeding.
5. `prompts/p1_requirements.txt` + `generate_reqs.py`. Iterate until schema compliance is clean on two consecutive runs.
6. `select_sdlc.py` with the 3-framing × 3-trial × 2-model matrix.
7. `validate.py` + `p3_critic.txt`.
8. `metrics.py` + `report.py` + figures.
9. `report/report.md` skeleton with every table/figure wired in.

**Checkpoint after each step.** Print a short summary of what was produced and stop for review — do not chain all nine steps unattended.

---

## 8. Report Skeleton (`report/report.md`)

1. Introduction & scope — chosen domain, chosen functionality, why
2. Methodology — corpus, retrieval, model, parameters, reproducibility
3. Part 1 results — requirements table, traceability matrix, reasoning samples
4. Part 2 results — SDLC recommendation, criteria scoring, framing-sensitivity analysis
5. Validation — 29148 audit, hallucination audit, scorer agreement
6. Discussion — where the LLM added value, where it failed, what a requirements engineer still must do
7. Threats to validity — small corpus, single domain, retrieval bias, no ground-truth SRS to compare against
8. Conclusion
9. Appendices — full prompts, sample raw responses, MANIFEST

Include a **limitations** section that concedes the LLM cannot elicit tacit stakeholder knowledge and therefore cannot replace elicitation. Examiners look for that concession.

---

## 9. README.md (generate this too)

Setup steps, `ollama pull` commands, how to run each stage, expected runtime, where outputs land, and a one-paragraph summary of findings once results exist.

---

## Non-negotiables

- Local models only.
- Every LLM call logged to `logs/llm_calls.jsonl`.
- Raw outputs immutable; corrections tracked separately.
- No requirement without either a `chunk_id` or `derived=true`.
- The validation layer ships. It is not optional polish.

---

## Implementation notes (deviations and decisions)

Recorded here so the report can defend them. Each was a measured call, not an oversight.

1. **`nfr_category` uses `"none"` rather than the em-dash `—` for functional
   requirements.** A 7B model emitting a bare em-dash inside JSON is an avoidable
   encoding-and-parsing risk; `"none"` round-trips through JSON and CSV cleanly.

2. **FAISS index is `flat_ip` over L2-normalised vectors, not `flat_l2`.** Ranking
   is identical (L2 is monotone in cosine for normalised vectors); the inner
   product just yields a bounded, reportable similarity score.

3. **Retrieval is faceted, not a single query.** The single-query strategy specified
   in §4 was implemented, measured, and rejected: it returns evidence from only 2 of
   6 documents. Both strategies remain selectable in `config/pipeline.yaml` and the
   comparison is reported. `top_k` was raised 12 → 16 accordingly.

4. **`num_ctx` is 16384, not 8192.** ~7k tokens of evidence plus the template plus
   20–25 requirements with per-requirement reasoning does not fit in 8k, and Ollama
   truncates silently — which would have quietly destroyed traceability.

5. **Part 2 trials vary the seed (42+trial), holding temperature at 0.1.** At a
   fixed seed all three trials would be byte-identical and the stability analysis
   would measure nothing.

6. **`MANIFEST.csv` carries three additive columns** (`bytes`, `n_sections`,
   `n_chunks`) beyond the specified schema; the report's corpus table needs them.
   `pages` is empty for HTML/XML sources, which have no pages.

7. **CFR sections are subdivided on top-level paragraph designators**, so citations
   resolve to `170.315(b)` rather than to the whole of §170.315.

8. **Requirement quality is measured, never repaired.** The Part 1 driver enforces
   schema and traceability integrity only. Repairing weak words or compound
   obligations at generation time would leave the 29148 audit with nothing to find.

9. **`human_adjudication` is left blank by the tooling**, with the top conflicts
   pre-extracted to `outputs/adjudication_worksheet.csv`. Populating it
   programmatically would fabricate a human judgement.

10. **Part 1's repair call now carries the evidence.** Ollama's `/api/generate` is
    stateless, so the repair prompt only ever saw the errors and the previous
    response. When the count directive asked it to "add requirements from evidence
    you have not covered", it had no evidence and invented a chunk id
    (`D05#S170.315(c)#c14`, which does not exist). The repair prompt now includes the
    evidence block, and the repair call runs with a larger context window because it
    carries both the evidence and the previous response.

11. **Citation-integrity failures are recorded and escalated, not fatal.** Making a
    fabricated chunk id abort the run meant the hallucination audit could never
    observe one, and one bad citation discarded 17 good requirements. Part 1 now
    aborts only on output it cannot use (see note 12 for the contract floors). Invalid
    citations are kept verbatim in `invalid_chunk_ids`,
    score 0 on `traceable`, are counted as fabricated by the hallucination audit, and
    put the requirement in the human review queue.

12. **A contract failure is recorded, not fatal, once a repair has been tried.** On the
    first full GPU run, both baselines had a usable set whose main fault was too
    few NFRs; the repair, told only how many NFRs were missing, returned a shorter set,
    and the run aborted, so the baseline comparison had nothing to measure. Now the
    attempt with fewer violations is kept (the repair on a tie), `part1_contract.json`
    records `contract_passed` and the remaining violations, and the metrics report
    them. The contract itself is unchanged; it judges the output instead of discarding
    it. Only a response with no usable requirements still aborts.

13. **Evidence quotes are matched on their words, not their spacing.** The HTML-to-text
    conversion leaves artefacts such as `" numberOfRepeatsAllowed "`, and models often
    wrap a quote in quotation marks. Run 1's audit called genuine FHIR quotes
    fabricated over spacing alone. Quotes now match on letters and digits only, which
    is still a verbatim test: a paraphrase stays fabricated.

14. **The extraction agent sees the project context, and its prompt no longer presets
    field values.** In Run 1 the extraction prompt's JSON example carried concrete
    values (`"volatility": "Low"`, `"priority": "Must"`, `"risk_class": "Standard"`)
    and the agent never saw the project context, so nearly every requirement was
    labelled low-volatility. The factor scorers read that column, every project looked
    stable, and the engine ranked Waterfall first for all three cases, the weekly-
    shipping refill app included. Every judged field now shows its allowed values
    instead of an example value, and the agent gets the same project context the SDLC
    agent already had. All judged fields were changed, not only volatility, so the fix
    is not aimed at one outcome; the engine's profiles and rules are untouched. Run 1
    is archived in `runs/` and the report says what it showed.

15. **Two metrics were wrong in Run 1 and are fixed.** `human_adjudicated` counted
    empty cells as verdicts (pandas reads them as NaN, which became the text "nan").
    `grounding_rate_valid_ids` checked cited ids against the Part 1 set instead of the
    set the framing matrix scored; framing runs now record their input file, and the
    metric is skipped for runs that did not.

---

# Part B — Alignment with the problem statement

The grading brief is the *Agentic AI LLM system for automated requirement
gathering, analysis and SDLC identification* problem statement. The brief is
written for the financial sector; this project keeps the healthcare e-prescribing
domain (the corpus, the regulatory depth and the Part 1/Part 2 experiments carry
over) and adopts the brief's architecture, process and evaluation one-for-one.
Everything in Part A remains: it becomes the single-prompt baseline and the
framing-robustness experiment that the multi-agent system is compared against.

## B.1 Mapping of the brief's twenty points

| # | Brief point | Where it lives |
|---|---|---|
| 1 | System scope and expected outputs | Three healthcare case studies under `cases/`; outputs per case under `outputs/cases/<id>/` (SRS, user stories, use cases, acceptance criteria, compliance matrix, risk register, RTM, SDLC recommendation) |
| 2 | Stakeholders and role-specific interview templates | `config/stakeholders.yaml` (topics and seed questions per role); personas per case in `cases/<id>/case.yaml` |
| 3 | Structured and unstructured inputs, sensitive data protected before the LLM | `cases/<id>/documents/` (meeting notes, emails, policy, legacy interface spec, incident report); `src/security.py` masks PHI before any agent sees it |
| 4 | Multi-agent architecture with a central orchestrator | `src/agents/` (13 agents) and `src/orchestrator.py` (coordinator, shared blackboard, execution order, approval gates) |
| 5 | Authorised, version-controlled knowledge base with source, jurisdiction, effective date, version, applicability | `corpus/MANIFEST.csv` (new columns), `config/controls.yaml` (control catalogue, every control resolved to a corpus section), `config/sdlc.yaml` (selection rules and workflow templates), `kb_version` in `config/pipeline.yaml` |
| 6 | Retrieval-grounded generation with citations, confidence and escalation | `src/agents/base.py` grounding helper; retrieval allowlist per agent; confidence scoring in `src/agents/validation.py`; low-confidence items go to the approval queue |
| 7 | Adaptive interviews with follow-ups on vague, incomplete or inconsistent answers | `src/agents/interaction.py` (two interview rounds; rule and LLM vagueness checks drive follow-ups) |
| 8 | Standard requirement structure | Requirement record: id, statement, categories, source stakeholder statements, business justification, priority, dependencies, assumptions, acceptance criteria, applicable regulations, risk level, confidence, approval status |
| 9 | Multi-label classification over 13 categories | `src/agents/classification.py` |
| 10 | Quality analysis; failures return to clarification | 29148 rules + ambiguity, testability, missing-source, undefined-term and missing-control checks; `src/agents/clarification.py` loops failing requirements back to their stakeholders (bounded rounds) |
| 11 | Compliance and security analysis; no final legal determinations | `src/agents/compliance.py`, `src/agents/security_privacy.py`; every regulatory interpretation is queued for the compliance officer |
| 12 | Requirement artefacts linked to stakeholder statements and documents | `src/agents/documentation.py` |
| 13 | SDLC decision factors | The brief's 13 factors, scored by two models with requirement-cited justifications |
| 14 | Hybrid SDLC engine: deterministic rules + MCDA + LLM explanation, ranked | `src/sdlc_engine.py`, `config/sdlc.yaml` |
| 15 | Project-specific SDLC workflow | Workflow templates + security and compliance overlays in `config/sdlc.yaml`, tailored per case |
| 16 | Human-in-the-loop controls: accept, reject, modify, regenerate | `src/agents/approval.py`, `src/approve.py` (CLI), approval tab in `src/app.py` |
| 17 | Platform security | `src/security.py` (masking, encrypted vault, injection defences, output filtering, agent permissions, source allowlist), RBAC and TOTP MFA in the UI, audit logs, model and KB versioning in each run manifest |
| 18 | Prototype stack | Ollama (LLM), plain-Python orchestrator, FAISS (vector store), SQLite (requirements store and approvals), rule engine, Gradio (web UI), Markdown documents |
| 19 | Evaluation | `src/evaluate.py`: extraction P/R/F1, completeness, ambiguity- and conflict-detection accuracy, control coverage, hallucination rate, citation correctness, SDLC accuracy, human correction rate, processing time, traceability coverage, injection attack success, baseline comparison |
| 20 | Advisory deployment, monitoring, re-evaluation | Every run writes a manifest (models with digests, KB version, config hash); all prompts, evidence, agent decisions and approvals are logged |

## B.2 Case studies

| Case | Functionality | Why it is in the set |
|---|---|---|
| `erx_issuance` | E-prescription issuance with drug-drug and drug-allergy checking | The original target: safety-critical, heavily regulated, low volatility |
| `epcs_signing` | Controlled-substance prescribing: identity proofing, two-factor signing, logical access control, audit | Regulation-dominated and security-dominated; a fixed third-party audit date |
| `refill_reminders` | Patient-facing medication refill reminders and renewal requests | Lower clinical risk, UX-driven and volatile, continuous delivery expected — a case where the right SDLC answer differs |

The three cases share the corpus but differ in the project characteristics that
drive SDLC selection, so the engine is tested on cases whose correct answers are
not all the same.

## B.3 What stays human

The system is advisory. These are never generated, because generating them would
fabricate the evidence the evaluation rests on:

- Review of each case's gold standard (`cases/<id>/gold.yaml`, field `reviewed_by`).
- The expert SDLC choice per case (`expert_sdlc` in the gold file).
- Every approval decision (accept, reject, modify, regenerate).
- The time a manual requirements analysis took (`manual_effort_minutes`).
- Stakeholder-satisfaction survey responses.
- The `human_adjudication` column from Part A.

The case materials (personas, documents, gold requirements) are synthetic and were
drafted with AI assistance. The report must say so, and the gold standards count
only once the author has reviewed them.

## B.4 Design decisions

1. **Simulated stakeholders are played by the second model.** Agents run on
   `qwen2.5:7b-instruct`, personas on `llama3.1:8b`, so the system is not
   interviewing itself. Personas answer only from a hidden fact sheet; facts marked
   `vague_first` are stated vaguely until the interviewer asks for specifics. That
   is how ambiguity detection gets a ground truth.
2. **Fact ids never reach the agents.** Persona answers carry the fact ids they used
   for scoring, but the blackboard's permission layer hides them from every agent.
3. **Quality is measured before and after clarification.** The clarification loop
   repairs requirements through stakeholders, which is legitimate RE practice, but
   the audit still reports the first-draft quality, so Part A's principle — measure,
   do not launder — survives.
4. **Deterministic rules and the MCDA are stated before any results exist.** The
   engine's profiles come from the brief's own condition table plus cited
   literature (Boehm & Turner 2003 home grounds, Boehm 1988, the Agile Manifesto
   principles). They must not be tuned after seeing outputs.
5. **Agents degrade instead of aborting.** Every agent validates its JSON, makes one
   repair attempt with the errors, and on failure records the failure and escalates
   the affected items. One malformed answer should not discard a whole case.
6. **Defences are measured, not assumed.** Each seeded injection is replayed with
   and without the defences to give an attack success rate for both.
7. **Determinism is pinned and recorded, not assumed.** Seeds fix sampling, but the same
   seed only reproduces tokens when the prompt, weights, Ollama build and GPU match. So
   the offline suite checks that prompts are byte-identical across processes, the Colab
   notebook pins Ollama and serves one request at a time, embeddings run on the CPU
   (GPU kernels can reorder near-tied retrieval hits), and every session records its
   commit, GPU, model digests and package versions. A Part 1 baseline that aborts is
   recorded as a result rather than retried, because with fixed seeds a retry repeats it;
   it is retried once only when the code has changed since.
