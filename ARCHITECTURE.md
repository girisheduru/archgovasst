# Architecture and workflows

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
    Review -->|"Extract cited evidence"| OpenAI["OpenAI"]
    Import -->|"Embed rule text and evidence guidance"| OpenAI
    API -.->|"Optional review and sample traces"| Arize["Arize AX"]
```

## Standards import

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
```

## Document review

The [review page](frontend/README.md) shows each checkpoint as the [review API](backend/README.md#document-review-api) returns it. The backend records the reviewer and decision at both checkpoints. You can download the JSON decision record at any checkpoint.

```mermaid
flowchart TD
    Upload["Upload a PDF or Word design and choose its type, declared tier, and optional standards date"] --> Parse["Extract text by PDF page or Word body block"]
    Parse --> Rules["Load the latest eligible version of each applicable rule from Chroma"]
    Rules --> Extract["Ask OpenAI for candidate quotes and citations"]
    Extract --> Validate["Check each quote against the cited page or block"]
    Validate --> Evidence{"Checkpoint 1: Confirm evidence?"}
    Evidence -->|"Reject"| Rejected["End review as rejected"]
    Evidence -->|"Confirm"| Policy["Compute findings and assessed risk from the declared tier and rules with missing evidence"]
    Policy --> Report{"Checkpoint 2: Approve report?"}
    Report -->|"Reject"| Rejected
    Report -->|"Approve"| Approved["End review as approved"]
```

On refresh, the browser uses the saved review ID to fetch the current state. A backend restart clears that state.

```mermaid
flowchart LR
    Refresh["Refresh the review tab"] --> Fetch["GET /api/reviews/{review_id}"]
    Fetch --> Exists{"Review still in memory?"}
    Exists -->|"Yes"| Restore["Restore the current review"]
    Exists -->|"No"| Upload["Upload the document to start again"]
```

## LangGraph nodes and edges

The [graph definition](backend/governance/agent/graph.py) registers six Python functions as nodes. Each node reads the shared [review state](backend/governance/agent/state.py) and returns the fields it updates. FastAPI parses the uploaded document before invoking the graph and supplies the text sections, document type, declared risk tier, and standards date as the initial state.

```mermaid
flowchart TD
    start(["START"]) --> prepare["prepare"]
    prepare --> extract["extract"]
    extract --> confirm["confirm"]
    confirm -.->|"confirmed"| check["check"]
    confirm -.->|"rejected"| finish(["END"])
    check --> report["report"]
    report --> approve["approve"]
    approve --> finish
```

| Node | What it does |
| --- | --- |
| `prepare` | Loads the applicable rule versions from Chroma using the document type and standards date. |
| `extract` | Calls OpenAI for candidate evidence, validates quoted text against the cited section, and sets the stage to `confirm_evidence`. |
| `confirm` | Pauses for the evidence decision, appends it to the audit history, and sets the stage to `confirmed` or `rejected`. |
| `check` | Applies policy rules to produce findings and calculate the assessed risk tier. |
| `report` | Sets the stage to `approve_report` so the generated findings are ready for the next reviewer decision. |
| `approve` | Pauses for the report decision, appends it to the audit history, and sets the final stage to `approved` or `rejected`. |

Solid arrows are fixed edges registered with `add_edge`. The dashed arrows are the two outcomes of the conditional edge registered with `add_conditional_edges`. After `confirm` resumes, `after_confirmation` reads the stage and sends the review to `check` or directly to `END`. Both report decisions follow the same fixed edge from `approve` to `END`. `START` and `END` mark the graph boundaries.

### How a decision resumes the graph

Both `confirm` and `approve` call `interrupt()`. LangGraph saves the paused state in the in-memory checkpointer under the review ID, which the API passes as the LangGraph thread ID. The decision endpoint checks that the submitted checkpoint is still pending, then resumes the same thread with `Command(resume=...)`. LangGraph re-enters the paused node and `interrupt()` returns the submitted decision.

```mermaid
sequenceDiagram
    participant UI as Review page
    participant API as FastAPI
    participant Graph as LangGraph
    participant Store as In-memory checkpointer
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
```

See the [frontend hosting guide](frontend/README.md#connect-to-a-hosted-backend) and the [Railway setup guide](backend/README.md#deploy-on-railway) for configuration.
