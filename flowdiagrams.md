# Architecture and workflows

## Diagram colors

| Color | Meaning |
| --- | --- |
| Blue | People, uploads, and browser interactions |
| Green | API and deterministic processing |
| Purple | OpenAI calls and LLM evidence extraction |
| Orange | Standards storage and saved review state |
| Amber | Validation branches and human decisions |
| Teal | Results and completed steps |
| Red | Rejection |
| Gray | Optional integrations and workflow boundaries |

Node labels and arrow labels also identify each step and decision.

## System architecture

```mermaid
flowchart LR
    User["Reviewer or standards maintainer"] --> UI["React frontend"]
    UI -->|"Uploads and decisions"| API["FastAPI"]
    API -->|"Checkpoints, reports, and import results"| UI
    API --> Review["LangGraph review"]
    API --> Import["Standards import"]
    Review <-->|"Save and resume review state"| Memory["In-memory checkpointer"]
    Review -->|"Read applicable rules"| Chroma["Chroma standards store"]
    Import -->|"Write rule versions"| Chroma
    Review -->|"Embed design passages and extract cited evidence"| OpenAI["OpenAI"]
    Import -->|"Embed rule text and evidence guidance"| OpenAI
    API -.->|"Optional review and sample traces"| Arize["Arize AX"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class User,UI user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class API,Review,Import process;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class Memory,Chroma store;
    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#3b0764,stroke-width:2px;
    class OpenAI llm;
    classDef optional fill:#f1f5f9,stroke:#64748b,color:#1e293b,stroke-width:2px;
    class Arize optional;
```

## Standards import

### RAG upload flow

Upload approved standards to build the knowledge store before starting a design review. This flow ends when rule versions and their embeddings are saved in Chroma.

The [standards upload page and CLI](backend/README.md#configure-document-reviews) use the same import logic.

```mermaid
flowchart TD
    Web["Upload approved Word standards at /standards"] --> Auth["Check the import token"]
    CLI["Run the standards import CLI with Word files"] --> Parse["Extract rule IDs, effective dates, statements, and evidence guidance"]
    Auth --> Parse
    Parse --> Duplicate{"Duplicate rule ID and effective date in the import?"}
    Duplicate -->|"Yes"| Reject["Reject the import"]
    Duplicate -->|"No"| Lookup["Look up existing rule versions in Chroma"]
    Lookup --> Embed["Generate embeddings with OpenAI"]
    Embed --> Save["Write records keyed by rule ID and effective date"]
    Save --> Result["Return counts of versions added and overwritten"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Web,CLI user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Auth,Parse process;
    classDef decision fill:#fef3c7,stroke:#a16207,color:#713f12,stroke-width:2px;
    class Duplicate decision;
    classDef rejected fill:#fee2e2,stroke:#dc2626,color:#7f1d1d,stroke-width:2px;
    class Reject rejected;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class Lookup,Save store;
    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#3b0764,stroke-width:2px;
    class Embed llm;
    classDef output fill:#ccfbf1,stroke:#0f766e,color:#134e4a,stroke-width:2px;
    class Result output;
```

## Document review

### Review flow

This flow starts with a solution design and reads the standards already imported into Chroma. Design passage ranking and evidence extraction run during this review.

The [review page](frontend/README.md) shows each checkpoint as the [review API](backend/README.md#document-review-api) returns it. The backend records the reviewer and decision at both checkpoints. You can download the JSON decision record at any checkpoint.

```mermaid
flowchart TD
    Upload["Upload a PDF or Word design and choose its type, declared tier, and optional standards date"] --> Parse["Extract text by PDF page or Word body block"]
    Parse --> Rules["Load the latest eligible version of each applicable rule from Chroma"]
    Rules --> Extract["Rank design passages for each rule and extract candidate quotes"]
    Extract --> Validate["Verify each quote against its source passage"]
    Validate -->|"Rules without verified quotes"| Full["Search the full design and verify any further quotes"]
    Validate -->|"Rules with verified quotes"| Evidence{"Checkpoint 1: Confirm evidence?"}
    Full --> Evidence
    Evidence -->|"Reject"| Rejected["End review as rejected"]
    Evidence -->|"Confirm"| Policy["Compute findings and assessed risk from the declared tier and rules with missing evidence"]
    Policy --> Report{"Checkpoint 2: Approve report?"}
    Report -->|"Reject"| Rejected
    Report -->|"Approve"| Approved["End review as approved"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Upload user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Parse,Validate,Policy process;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class Rules store;
    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#3b0764,stroke-width:2px;
    class Extract,Full llm;
    classDef decision fill:#fef3c7,stroke:#a16207,color:#713f12,stroke-width:2px;
    class Evidence,Report decision;
    classDef rejected fill:#fee2e2,stroke:#dc2626,color:#7f1d1d,stroke-width:2px;
    class Rejected rejected;
    classDef output fill:#ccfbf1,stroke:#0f766e,color:#134e4a,stroke-width:2px;
    class Approved output;
```

The [retrieval architecture](ARCHITECTURE.md#rule-selection-and-evidence-retrieval) shows how every applicable rule stays in scope. On refresh, the browser uses the saved review ID to fetch the current state. A backend restart clears that state.

```mermaid
flowchart LR
    Refresh["Refresh the review tab"] --> Fetch["GET /api/reviews/{review_id}"]
    Fetch --> Exists{"Review still in memory?"}
    Exists -->|"Yes"| Restore["Restore the current review"]
    Exists -->|"No"| Upload["Upload the document to start again"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Refresh,Upload user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Fetch process;
    classDef decision fill:#fef3c7,stroke:#a16207,color:#713f12,stroke-width:2px;
    class Exists decision;
    classDef output fill:#ccfbf1,stroke:#0f766e,color:#134e4a,stroke-width:2px;
    class Restore output;
```

## LangGraph nodes and edges

The [graph definition](backend/governance/agent/graph.py) registers six Python functions as nodes. Each node reads the shared [review state](backend/governance/agent/state.py) and returns the fields it updates. FastAPI parses the uploaded document before invoking the graph and supplies the text sections, document type, declared risk tier, and standards date as the initial state.

```mermaid
flowchart TD
    start(["START"]) --> prepare["retrieve_applicable_rules"]
    prepare --> extract["extract_evidence_with_llm"]
    extract --> confirm["confirm_evidence"]
    confirm -.->|"confirmed"| check["assess_evidence_gaps"]
    confirm -.->|"rejected"| finish(["END"])
    check --> report["mark_report_ready"]
    report --> approve["approve_report"]
    approve --> finish

    classDef optional fill:#f1f5f9,stroke:#64748b,color:#1e293b,stroke-width:2px;
    class start,finish optional;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class prepare store;
    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#3b0764,stroke-width:2px;
    class extract llm;
    classDef decision fill:#fef3c7,stroke:#a16207,color:#713f12,stroke-width:2px;
    class confirm,approve decision;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class check,report process;
```

| Node | What it does |
| --- | --- |
| `retrieve_applicable_rules` | Retrieves the latest effective version of every applicable rule from Chroma. |
| `extract_evidence_with_llm` | Ranks design passages per rule, extracts quotes with an LLM, and verifies them against the source text. It searches the full design for unresolved rules before setting the stage to `confirm_evidence`. |
| `confirm_evidence` | Pauses for the evidence decision, appends it to the audit history, and sets the stage to `confirmed` or `rejected`. |
| `assess_evidence_gaps` | Applies policy rules to produce findings and calculate the assessed risk tier. |
| `mark_report_ready` | Sets the stage to `approve_report` so the generated findings are ready for the next reviewer decision. |
| `approve_report` | Pauses for the report decision, appends it to the audit history, and sets the final stage to `approved` or `rejected`. |

Solid arrows are fixed edges registered with `add_edge`. The dashed arrows are the two outcomes of the conditional edge registered with `add_conditional_edges`. After `confirm_evidence` resumes, `after_confirmation` reads the stage and sends the review to `assess_evidence_gaps` or directly to `END`. Both report decisions follow the same fixed edge from `approve_report` to `END`. `START` and `END` mark the graph boundaries.

### How a decision resumes the graph

Both `confirm_evidence` and `approve_report` call `interrupt()`. LangGraph saves the paused state in the in-memory checkpointer under the review ID, which the API passes as the LangGraph thread ID. The decision endpoint checks that the submitted checkpoint is still pending, then resumes the same thread with `Command(resume=...)`. LangGraph re-enters the paused node and `interrupt()` returns the submitted decision.

```mermaid
sequenceDiagram
    box rgb(219, 234, 254)
        participant UI as Review page
    end
    box rgb(220, 252, 231)
        participant API as FastAPI
    end
    box rgb(220, 252, 231)
        participant Graph as LangGraph
    end
    box rgb(255, 237, 213)
        participant Store as In-memory checkpointer
    end
    Graph->>Store: Save paused state under the review ID
    Graph-->>API: Return state at the pending checkpoint
    API-->>UI: Show evidence or report for review
    UI->>API: POST the checkpoint decision
    API->>Graph: Read current state for that review ID
    Graph->>Store: Load saved state
    Graph-->>API: Return current checkpoint
    alt Checkpoint is still pending
        API->>Graph: Resume the same thread with the decision
        Graph->>Graph: Return decision from interrupt and follow the next edge
        Graph-->>API: Return the next checkpoint or final state
        API-->>UI: Show the updated review
    else Checkpoint has already been decided
        API-->>UI: Return HTTP 409 and prompt a refresh
    end
```

## Sample review

```mermaid
flowchart LR
    Client["API client"] --> Request["GET /api/reviews/sample"]
    Request --> Select["Select a fictional system and findings"]
    Select --> Response["Return sample JSON with findings and next steps"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Client user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Request,Select process;
    classDef output fill:#ccfbf1,stroke:#0f766e,color:#134e4a,stroke-width:2px;
    class Response output;
```

## Report evaluation

The [evaluation CLI](backend/README.md#evaluate-an-exported-report) scores a report after it has been generated.

```mermaid
flowchart TD
    Record["Exported JSON record with a report"] --> Evaluate["Evaluation CLI"]
    Source["Original design document"] --> Evaluate
    Key["Human answer key"] --> Evaluate
    Evaluate --> Rules["Load applicable rules using the recorded date and document type"]
    Rules --> Metrics["Score missing evidence, risk tier agreement, rule coverage, and citation validity"]
    Metrics --> Judge{"Optional OpenAI judge enabled?"}
    Judge -->|"Yes"| OpenAI["Score clarity, actionability, and hallucination risk"]
    Judge -->|"No"| Output["Print JSON scores"]
    OpenAI --> Output

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Record,Source,Key user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Evaluate,Metrics process;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class Rules store;
    classDef decision fill:#fef3c7,stroke:#a16207,color:#713f12,stroke-width:2px;
    class Judge decision;
    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#3b0764,stroke-width:2px;
    class OpenAI llm;
    classDef output fill:#ccfbf1,stroke:#0f766e,color:#134e4a,stroke-width:2px;
    class Output output;
```

## Local and hosted request flow

```mermaid
flowchart TD
    Local["Local browser session"] --> Vite["Vite development server"]
    Vite -->|"Forward /api requests"| LocalAPI["Local FastAPI on port 8000"]
    Hosted["Hosted browser session"] --> Vercel["Vercel serves the React app"]
    Vercel --> Browser["React app sends requests from the browser"]
    Browser -->|"Configured HTTPS API URL through your gateway"| Railway["FastAPI on Railway"]
    Railway --> Chroma["Chroma Cloud or private Chroma service"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Local,Hosted,Browser user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Vite,LocalAPI,Vercel,Railway process;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class Chroma store;
```

See the [frontend hosting guide](frontend/README.md#connect-to-a-hosted-backend) and the [Railway setup guide](backend/README.md#deploy-on-railway) for configuration.
