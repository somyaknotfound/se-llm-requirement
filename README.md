# LLM-Assisted Requirements Engineering & SDLC Selection

A local-only pipeline that grounds a small LLM on real healthcare requirement
sources, generates a traceable requirement set for **electronic prescription (e-Rx)
issuance**, feeds that set back to select an SDLC model under three prompt framings,
and then audits everything the model produced against ISO/IEC/IEEE 29148.

**No hosted LLM API is used anywhere.** All inference runs locally through Ollama.

---

## Prerequisites

- **Python 3.11+** (developed on 3.12.5, Windows 11)
- **[Ollama](https://ollama.com/download)** installed and running locally
- ~10 GB free disk (two models + torch + the embedding model)

---

## Setup

### 1. Install Ollama and pull both models

Both models are required: the second exists so Part 2 can measure cross-model
agreement, which a single model cannot provide.

```bash
ollama pull qwen2.5:7b-instruct
```

```bash
ollama pull llama3.1:8b
```

Verify the daemon is up and both models are present (this output is also the
evidence of local execution the report cites):

```bash
ollama list
```

If the daemon is not running, start it with `ollama serve`.

### 2. Create the environment

```bash
python -m venv .venv
```

Windows (PowerShell):

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

### 3. Optional configuration

```bash
cp .env.example .env
```

Set `HF_HOME` if your user profile is on a small or cloud-synced drive — the
embedding model caches ~90 MB. Set `PROTECT_OUTPUTS=1` to make the drivers refuse
to overwrite existing artifacts.

---

## Running the pipeline

Each stage is independent and writes its own artifacts. Run them in order.

### Stage 0 — smoke-test the transport

Do this first; nothing else works if it is flaky.

```bash
python -m src.llm --smoke
```

Expect a JSON round-trip from both models, with latency and token counts, plus a
line appended to `logs/llm_calls.jsonl`.

### Stage 1 — build the corpus

```bash
python -m src.ingest all
```

Downloads 6 source documents to `corpus/raw/`, records provenance and SHA-256 in
`corpus/MANIFEST.csv`, cleans to `corpus/processed/`, and chunks to
`corpus/chunks.jsonl`. Chunk ids are verified unique and round-tripping.

*Requires network access. ~30 seconds.*

### Stage 2 — build and sanity-check the index

```bash
python -m src.index build
```

```bash
python -m src.index sanity
```

The sanity check runs three probe queries and prints the top hits. **Read the
output.** The queries should surface §1311.140 (signing controlled substances),
§170.315(a) (CPOE — medications) and the FHIR audit-logging section. If they do
not, retrieval is miscalibrated and everything downstream inherits the fault.

*First run downloads the embedding model (~90 MB). ~1 minute.*

### Stage 3 — Part 1: generate requirements

```bash
python -m src.generate_reqs
```

Inspect the assembled prompt without calling a model:

```bash
python -m src.generate_reqs --dry-run
```

Produces `outputs/requirements.csv`, `outputs/requirements_reasoning.csv`,
`outputs/traceability_matrix.csv`, and the raw response at
`outputs/raw_p1_response.txt`.

The driver enforces the output contract and will make **one** repair attempt before
aborting. It deliberately does *not* repair requirement quality — that is what
Stage 5 measures.

*~2–5 minutes on CPU.*

### Stage 4 — Part 2: SDLC selection matrix

```bash
python -m src.select_sdlc
```

3 framings × 3 trials × 2 models = 18 runs. Produces `outputs/sdlc_analysis.csv`
(one row per criterion) and `outputs/sdlc_runs.csv` (one row per run).

*~20–45 minutes on CPU. This is the long stage.*

### Stage 5 — validation

```bash
python -m src.validate all
```

Runs the rule-based 29148 scorer, the LLM critic (one call per requirement on a
fresh context), and the hallucination audit. Produces
`outputs/validation_29148.csv`, `outputs/hallucination_audit.csv` and
`outputs/adjudication_worksheet.csv`.

The rule scorer alone needs no model:

```bash
python -m src.validate rules
```

**Manual step:** open `outputs/adjudication_worksheet.csv`, resolve ~10 conflicts by
hand, and copy your verdicts into the `human_adjudication` column of
`outputs/validation_29148.csv`. The tooling leaves this blank on purpose — filling
it automatically would fabricate a human judgement.

*~5–10 minutes.*

### Stage 6 — metrics and figures

```bash
python -m src.metrics
```

```bash
python -m src.report
```

Writes `outputs/metrics_summary.csv`, figures to `figures/`, and generated tables to
`report/tables.md`. Both are safe to run at any point — stages whose inputs are
missing are skipped.

---

## Where outputs land

| Path | Contents |
|---|---|
| `corpus/MANIFEST.csv` | Provenance: source URL, licence, SHA-256, retrieval date |
| `corpus/chunks.jsonl` | Chunked corpus with `chunk_id`, section and token count |
| `outputs/requirements.csv` | The requirement set (12-column schema) |
| `outputs/requirements_reasoning.csv` | Per-requirement reasoning, evidence quote, inference type |
| `outputs/traceability_matrix.csv` | Requirements × source documents (D / I / blank) |
| `outputs/sdlc_analysis.csv` | Per-criterion scores across all 18 runs |
| `outputs/sdlc_runs.csv` | One row per run: recommendation, runner-up, counterargument |
| `outputs/validation_29148.csv` | Both scorers, agreement, adjudication column |
| `outputs/hallucination_audit.csv` | Every citation with a verdict and severity |
| `outputs/metrics_summary.csv` | All headline numbers |
| `logs/llm_calls.jsonl` | Every call: params, full prompt, raw response, latency |
| `figures/` | Traceability heatmap, pass rates, framing sensitivity |
| `report/report.md` | The writeup |

---

## Design decisions worth knowing

**Faceted retrieval, not a single query.** A single query built from the
functionality description plus all keywords returns evidence from only two of six
documents — the centroid lands in the largest document's region of the space. Seven
facet queries interleaved round-robin span five. Both modes are in
`config/pipeline.yaml`; the comparison is reported rather than hidden.

**Quality is measured, not repaired.** The Part 1 driver enforces schema and
traceability integrity but leaves weak words and compound obligations intact. If
generation repaired them, the 29148 audit would have nothing to find and would be
theatre.

**Trials vary the seed, not the temperature.** At temperature 0.1 with a fixed seed,
three trials would be byte-identical. Raising the temperature would confound
sampling noise with framing sensitivity. Stepping the seed isolates it.

**Two 29148 attributes are weakly decidable by rule.** `necessary` and `feasible`
need judgement a regex cannot supply. Those rows are tagged in the CSV rather than
being presented as measurements.

**Malformed Part 2 runs are recorded, not re-rolled.** Re-rolling until the output
parses would bias the stability statistic the matrix exists to measure.

---

## Summary of findings

`[Populate once the pipeline has been run end-to-end.]` State the requirement
count and traceability rate, the modal SDLC recommendation and its flip rate under
framing, the 29148 pass rates and scorer agreement, and — first — the hallucination
audit result, since fabricated regulatory citations in a healthcare context are a
safety argument rather than a nitpick.

---

## Troubleshooting

**`cannot reach Ollama at http://127.0.0.1:11434`** — the daemon is not running.
Start it with `ollama serve`, then re-run `python -m src.llm --smoke`.

**`required models are not present in the local Ollama registry`** — run the
`ollama pull` commands above. The driver refuses to silently substitute a fallback,
because that would make the report's model attribution false. Declared fallbacks are
listed in `config/models.yaml` and must be selected deliberately.

**`sha256 mismatch vs MANIFEST.csv`** — a source document changed upstream or was
edited locally. Re-run `python -m src.ingest fetch` to re-record provenance, and note
in the report that the corpus was re-acquired.

**Part 1 aborts after repair** — read `outputs/raw_p1_repair_response.txt` and the
printed violations. A 7B model failing the contract twice is itself a reportable
result; do not loosen the contract to make it pass.
