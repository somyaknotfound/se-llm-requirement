# Agentic Requirements Engineering & SDLC Selection for e-Prescribing

A local-LLM, multi-agent system that gathers and analyses requirements for healthcare
e-prescribing functionality and recommends a software development life cycle, built to
the *Agentic AI–based LLM system for automated requirement gathering, analysis and SDLC
identification* problem statement (mapped point by point in [BUILD.md, Part B](BUILD.md)).

Specialised agents interview stakeholders, extract requirements from conversations and
documents, ask clarification questions, detect conflicts, classify requirements across
13 categories, map them to HIPAA, ONC and DEA controls, threat-model them, assess risk,
audit them against ISO/IEC/IEEE 29148, recommend an SDLC with a ranked, rule-backed
justification and a project-specific workflow, generate the SRS and supporting artefacts,
and route every decision that needs a person to the right approver.

**No hosted LLM API is used anywhere.** All inference runs locally through Ollama.
The system is advisory: requirement baselines, regulatory interpretations and SDLC
adoption stay with authorised humans.

---

## Run it on Colab (recommended)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/somyaknotfound/se-llm-requirement/blob/main/notebooks/run_on_colab.ipynb)

Set `Runtime -> Change runtime type -> T4 GPU`, then run the cells in order. Setup takes
about 15 minutes, each case study 30–45 minutes, the SDLC framing matrix about 15.
Download the results zip at the end — Colab destroys `/content` when the runtime ends.

---

## What is in the box

| Part | What it does | Code |
|---|---|---|
| Knowledge base | 6 openly licensed sources (HL7 FHIR R4, HIPAA Security Rule, ONC 170.315, DEA 21 CFR 1311) with jurisdiction, effective date, version and applicability; a 45-control catalogue tied to corpus sections; SDLC rules and workflow templates | `corpus/`, `config/controls.yaml`, `config/sdlc.yaml` |
| Case studies | e-Rx issuance, controlled-substance signing (EPCS), patient refill reminders — personas, documents, seeded defects, gold standards | `cases/` |
| Multi-agent system | 13 agents under a coordinator, with a permissioned blackboard | `src/agents/`, `src/orchestrator.py` |
| Security | PHI masking with an encrypted vault, prompt-injection quarantine and delimiting, output leak checks, agent permissions, source allowlists, RBAC + TOTP two-factor sign-in | `src/security.py`, `src/approve.py` |
| SDLC engine | The brief's 13 decision factors → deterministic rules + MCDA → ranked percentages → tailored workflow | `src/sdlc_engine.py` |
| Human in the loop | Approval queue in SQLite; accept, reject, modify, regenerate; web UI | `src/store.py`, `src/approve.py`, `src/app.py` |
| Baseline | The original single-prompt generator, now the comparison point | `src/generate_reqs.py` |
| Evaluation | P/R/F1 against gold, ambiguity and conflict detection, control coverage, hallucination rate, SDLC accuracy, injection attack success, and more | `src/evaluate.py` |

### The agents

| Agent | Responsibility |
|---|---|
| Coordinator | Execution order, shared state, approval gates, checkpoints (`src/orchestrator.py`) |
| Stakeholder interaction | Role-specific interviews; follow-ups on vague, incomplete or inconsistent answers |
| Requirement extraction | Requirements from each stakeholder and document, grounded in retrieved evidence |
| Clarification | Sends requirements that fail quality checks back to their stakeholder |
| Classification | Multi-label classification into 13 categories |
| Conflict detection | Duplicates (merged) and contradictions (flagged for a human) |
| Compliance | Control mappings with evidence, compliance gaps, gap proposals |
| Security and privacy | STRIDE threat analysis, requirements for unmitigated threats |
| Risk analysis | Risk register with likelihood × impact banding |
| Validation | 29148 audit (rules + LLM critic), hallucination audit, confidence, escalation |
| SDLC selection | Factor scoring by two models → engine → explanation → workflow |
| Documentation | SRS, user stories, use cases, RTM, compliance matrix, registers |
| Human approval | Routes every decision that needs a person to the role with authority |

---

## Running locally

### Prerequisites

- Python 3.11+ (developed on 3.12, Windows 11)
- [Ollama](https://ollama.com/download) running locally, with both models pulled:

```bash
ollama pull qwen2.5:7b-instruct
```

```bash
ollama pull llama3.1:8b
```

### Setup

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

(`.venv/bin/python` on macOS/Linux.) The offline test suite needs no model:

```bash
python -m pytest -q
```

### The pipeline

```bash
python -m src.llm --smoke
python -m src.index build && python -m src.index sanity
```

Baseline (single prompt), on the original target and on a case study:

```bash
python -m src.generate_reqs
python -m src.generate_reqs --case epcs_signing
python -m src.validate all --case epcs_signing
```

The multi-agent system (one case, or all; `--resume` continues an interrupted run):

```bash
python -m src.orchestrator --case erx_issuance
python -m src.orchestrator --case all --resume
```

Experiments:

```bash
python -m src.select_sdlc --reqs outputs/cases/erx_issuance/requirements.csv
python -m src.evaluate --case all --injection-replay
python -m src.metrics && python -m src.report
```

### Human review

```bash
python -m src.approve add-user --user laura --role compliance_officer
python -m src.app            # web UI: sign in, approval queue, artefacts, live interview, survey
python -m src.approve list --case erx_issuance --user laura
python -m src.approve decide --case erx_issuance --user laura APR-014 accept --note "mapping confirmed"
python -m src.orchestrator --case erx_issuance --apply-decisions
```

Sign-in needs the password and a six-digit code from an authenticator app (the secret is
printed by `add-user`). Reviewer accounts live in `config/users.local.yaml`, which is
never committed.

---

## Where outputs land

| Path | Contents |
|---|---|
| `outputs/cases/<case>/artifacts/` | `srs.md`, `user_stories.md`, `use_cases.md`, `process_workflow.md`, `rtm.csv`, `compliance_matrix.csv`, `risk_register.csv`, `threat_register.csv`, `assumptions_dependencies.csv`, `open_issues.csv`, `data_requirements.md`, `interface_requirements.md`, `sdlc_recommendation.md` |
| `outputs/cases/<case>/re.db` | SQLite store of record: requirements, statements, findings, conflicts, compliance, risks, approvals, decisions |
| `outputs/cases/<case>/state.json` | The full blackboard, checkpointed after every step |
| `outputs/cases/<case>/agent_log.jsonl` | Every agent action with its LLM call ids |
| `outputs/cases/<case>/run_manifest.json` | Timings, model digests, knowledge-base fingerprint |
| `outputs/cases/<case>/baseline/` | The single-prompt baseline for the case, validated |
| `outputs/cases/<case>/matches_*.csv` | Automatic gold matches with an empty `human_verdict` column |
| `outputs/evaluation/` | `summary.csv`, `summary_wide.csv`, `injection_replay.csv`, survey responses |
| `outputs/` (root) | Part 1 baseline, Part 2 framing matrix, `sdlc_consistency.csv`, `metrics_summary.csv` |
| `logs/llm_calls.jsonl` | Every model call: parameters, full prompt, raw response, latency |

---

## What stays human

Generating any of these would fabricate the evidence the evaluation rests on, so the code
never does:

- reviewing each case's gold standard (`cases/<case>/gold.yaml` → `reviewed_by`)
- the expert SDLC choice per case (`expert_sdlc`) and your manual-analysis time (`manual_effort_minutes`)
- verifying automatic matches (`human_verdict` in `matches_*.csv`)
- every approval decision, and the satisfaction survey
- `human_adjudication` in the Part 1 validation worksheet

The case materials are synthetic and were drafted with AI assistance; the report must say so.

---

## Design decisions worth knowing

**The model perceives, the engine decides.** Two models score the 13 decision factors;
the SDLC choice is made by transparent rules and weighted scoring stated before any
results existed; the model only explains it. Whether a model's own free-text pick
follows from its own scores is itself measured.

**Quality is measured before and after clarification.** The clarification loop repairs
requirements through their stakeholders, but the first-draft 29148 audit is reported
too — the loop's effect is a result, not a way of hiding the model's first attempt.

**Simulated stakeholders run on the second model**, answer only from a hidden fact sheet,
and state some facts vaguely until the system follows up. That gives ambiguity and
conflict detection a ground truth. Fact ids are stripped before any agent sees a statement.

**Integrity failures are recorded, not fatal.** A citation to a chunk the model was never
shown is kept in `invalid_chunk_ids`, counted by the hallucination audit, and escalated.
Only unusable output (unparseable, wrong schema, wrong count) aborts Part 1.

**Defences are measured.** Each seeded prompt injection is replayed with and without the
quarantine-and-delimiting defences to give an attack success rate for both.

**Faceted retrieval, not a single query.** One centroid query retrieved from 2 of 6
documents; seven facet queries interleaved round-robin reach 5. Each case study defines
its own facets and knowledge-source allowlist.

---

## Troubleshooting

**`cannot reach Ollama at http://127.0.0.1:11434`** — start the daemon with `ollama serve`.

**`required models are not present`** — pull both models; the code never substitutes a
fallback silently.

**Part 1 aborts after repair** — the output was unusable twice (not parseable, wrong
schema, or outside the 18–25 count). Read `raw_p1_repair_response.txt`; that is a
reportable result about a 7B model, not something to loosen the contract for. Citation
problems alone no longer abort: they are flagged in `invalid_chunk_ids` and escalated.

**A case run was interrupted** — `python -m src.orchestrator --case <case> --resume`.

**`sha256 mismatch vs MANIFEST.csv`** — a source changed upstream; re-fetch with
`python -m src.ingest fetch` and note the re-acquisition in the report.
