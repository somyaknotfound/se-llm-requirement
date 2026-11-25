# Architecture

## 1. System layers: front end to back end

```mermaid
flowchart TB
    subgraph FE["Front end"]
        UI["Web UI (Gradio)<br/>src/app.py"]
        CLI["Review CLI<br/>src/approve.py"]
        OPS["Operator CLI<br/>src/orchestrator.py, src/evaluate.py"]
    end
    subgraph SEC["Security layer - src/security.py"]
        AUTH["Password (PBKDF2) + TOTP<br/>role-based access"]
        MASK["PHI masking"]
        INJ["Prompt-injection quarantine"]
    end
    subgraph APP["Application layer"]
        COORD["Coordinator agent<br/>src/orchestrator.py"]
        BB[("Blackboard<br/>least-privilege slots")]
        AG["12 specialist agents<br/>src/agents/"]
        SDLC["SDLC engine: rules + MCDA<br/>src/sdlc_engine.py"]
    end
    subgraph AI["AI layer"]
        LLM["Local models via Ollama<br/>qwen2.5:7b, llama3.1:8b"]
        RAG["Retriever: MiniLM + FAISS<br/>src/index.py"]
    end
    subgraph DATA["Data layer"]
        KB["Corpus: FHIR, HIPAA, ONC, DEA<br/>45-control catalogue"]
        DB[("SQLite re.db<br/>approvals, decisions")]
        FILES["state.json, artefacts,<br/>agent log, model-call log"]
    end
    UI --> AUTH
    CLI --> AUTH
    OPS --> COORD
    AUTH --> COORD
    AUTH --> DB
    COORD --> MASK --> INJ --> BB
    COORD --> AG
    AG <--> BB
    AG --> LLM
    AG --> RAG
    RAG --> KB
    AG --> SDLC
    COORD --> FILES
    COORD --> DB
```

## 2. One case, end to end

```mermaid
sequenceDiagram
    actor R as Reviewer
    participant W as Web UI
    participant C as Coordinator
    participant A as Agents
    participant M as Local LLMs
    participant D as SQLite and files
    R->>W: password + one-time code
    W-->>R: signed in with roles
    R->>W: run case
    W->>C: start pipeline
    C->>C: intake: mask PHI, quarantine injections
    C->>A: interview stakeholders
    A->>M: questions, follow-ups, extraction
    M-->>A: JSON (checked, one repair attempt)
    A->>A: classify, find conflicts, audit, clarify
    A->>A: compliance, threats, risks, validation
    A->>A: SDLC factor scores, rules + MCDA
    C->>D: SRS, RTM, registers, approval queue
    R->>W: accept / modify / reject, with a note
    W->>D: decision + user + role + time
    R->>W: apply decisions
    W->>C: update requirements, rebuild artefacts
    C->>D: new versions, full history
    R->>W: evaluate against the gold standard
    W-->>R: multi-agent vs single-prompt baseline
```

## 3. The 14 pipeline steps

```mermaid
flowchart LR
    subgraph G1["Gather"]
        direction TB
        S1["1 Intake: mask, quarantine"] --> S2["2 Interviews, 2 rounds"] --> S3["3 Extraction, grounded in corpus"] --> S4["4 Classification, 13 categories"]
    end
    subgraph G2["Analyse"]
        direction TB
        S5["5 Conflicts and duplicates"] --> S6["6 First-draft 29148 audit"] --> S7["7 Clarification: back to stakeholders"] --> S8["8 Compliance: 45 controls"]
    end
    subgraph G3["Assure"]
        direction TB
        S9["9 STRIDE threat model"] --> S10["10 Risk register"] --> S11["11 Final audit, hallucination check"]
    end
    subgraph G4["Decide"]
        direction TB
        S12["12 SDLC: scores, rules, MCDA"] --> S13["13 Documentation, 13 artefacts"] --> S14["14 Human approval queue"]
        S14 -. apply decisions .-> S13
    end
    G1 --> G2 --> G3 --> G4
```

The model perceives, the engine decides: both models only score 13 project factors; a
transparent rules and weighted-scoring engine ranks the SDLC models, and people sign it off.
