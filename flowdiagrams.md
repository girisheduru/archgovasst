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
    UI -->|"Uploads, decisions, and confirmed standards resets"| API["FastAPI"]
    API -->|"Checkpoints, reports, and standards results"| UI
    API --> Review["LangGraph review"]
    API --> Import["Standards import and reset"]
    Review <-->|"Save and resume review state"| Memory["In-memory checkpointer"]
    Review -->|"Read applicable rules"| Chroma["Chroma standards store"]
    Import -->|"Write rule versions or delete the standards collection"| Chroma
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
    Web["Select Word standards and display all filenames at /standards"] --> Auth["Check the import token"]
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

### RAG database reset

```mermaid
flowchart LR
    Clear["Select Clear RAG database"] --> Confirm{"Confirm permanent deletion?"}
    Confirm -->|"Cancel"| Cancel["Show cancellation"]
    Confirm -->|"Confirm"| Auth["Check the import token"]
    Auth --> Delete["Delete the configured Chroma standards collection"]
    Delete --> Result["Report cleared, already empty, or failed"]
```

## Document review

### Review flow

This flow starts with a solution design and reads the standards already imported into Chroma. Design passage ranking and evidence extraction run during this review.

The [review page](frontend/README.md) shows each checkpoint as the [review API](backend/README.md#document-review-api) returns it. Reviewers can filter and expand findings at either checkpoint, then submit their decision and any draft comments using the visible **Record decision** form. The backend records the reviewer and decision at both checkpoints. You can download the JSON decision record at any checkpoint.

```mermaid
flowchart TD
    Upload["Upload a PDF or Word design and choose its type, declared tier, and optional standards date"] --> Parse["Extract text by PDF page or Word body block"]
    Parse --> Rules["Load the latest eligible version of each applicable rule from Chroma"]
    Rules --> Extract["Rank design passages for each rule and extract candidate quotes"]
    Extract --> Validate["Verify each quote against its source passage"]
    Validate -->|"Rules without verified quotes"| Full["Search the full design and verify any further quotes"]
    Validate -->|"Rules with verified quotes"| Evidence{"Checkpoint 1: Confirm evidence?"}
    Full --> Evidence
    Evidence -.->|"Optional for a rule with a gap"| Guidance["Draft guidance from the rule and relevant design passages"]
    Evidence -.->|"Optional for a rule with a gap"| Recheck["Check a supporting document and stage a verified quote"]
    Recheck -.-> Evidence
    Evidence -->|"Reject"| Rejected["End review as rejected"]
    Evidence -->|"Confirm"| Policy["Compute findings and assessed risk from the declared tier and rules with missing evidence"]
    Policy --> Report{"Checkpoint 2: Approve report?"}
    Report -->|"Reject"| Rejected
    Report -->|"Approve"| Approved["End review as approved"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Upload user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Parse,Validate,Policy,Recheck process;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class Rules store;
    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#3b0764,stroke-width:2px;
    class Extract,Full,Guidance llm;
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
| `confirm_evidence` | Pauses for the evidence decision, includes any selected supporting quotes when confirmed, appends the decision to the audit history, and sets the stage to `confirmed` or `rejected`. |
| `assess_evidence_gaps` | Applies policy rules to produce findings and calculate the assessed risk tier. |
| `mark_report_ready` | Sets the stage to `approve_report` so the generated findings are ready for the next reviewer decision. |
| `approve_report` | Pauses for the report decision, appends it to the audit history, and sets the final stage to `approved` or `rejected`. |

Solid arrows are fixed edges registered with `add_edge`. The dashed arrows are the two outcomes of the conditional edge registered with `add_conditional_edges`. After `confirm_evidence` resumes, `after_confirmation` reads the stage and sends the review to `assess_evidence_gaps` or directly to `END`. Both report decisions follow the same fixed edge from `approve_report` to `END`. `START` and `END` mark the graph boundaries.

### How a decision resumes the graph

The graph pauses twice for a reviewer’s decision. The first pause confirms the evidence. The second approves the report.

#### Pause for review

The checkpoint node calls `interrupt()`. LangGraph saves the review state in backend memory, and the page shows what the reviewer needs to decide.

```mermaid
flowchart TD
    Pause["Graph pauses"] --> Save["Save review state"]
    Save --> Show["Show evidence or report"]

    classDef decision fill:#fef3c7,stroke:#a16207,color:#713f12,stroke-width:2px;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Pause decision;
    class Save store;
    class Show user;
```

#### Continue after a decision

The reviewer submits a decision. FastAPI checks that the checkpoint is still pending, then passes the decision to the saved graph using `Command(resume=...)`.

```mermaid
flowchart TD
    Submit["Reviewer submits decision"] --> Check["API checks pending checkpoint"]
    Check --> Resume["Resume saved graph"]
    Resume --> Continue["Continue with the decision"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    classDef output fill:#ccfbf1,stroke:#0f766e,color:#134e4a,stroke-width:2px;
    class Submit user;
    class Check,Resume process;
    class Continue output;
```

LangGraph uses the review ID to find the saved state. It restarts the paused node, where `interrupt()` returns the submitted decision.

| Decision | What happens next |
| --- | --- |
| Confirm evidence | Calculate findings and risk, then pause for report approval. |
| Reject evidence | End the review as rejected. |
| Approve or reject the report | End the review with that final decision. |

If the checkpoint has already been decided, the API returns HTTP 409 and the reviewer must refresh the page. A backend restart clears the saved state, so the document must be uploaded again.

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

## Arize AX benchmark

The [benchmark runner](backend/README.md#run-the-arize-ax-benchmark) publishes assets and runs the same evidence extraction and gap assessment functions used by live reviews.

```mermaid
flowchart LR
    Startup["FastAPI startup or standalone publishing command"] --> Publisher
    Workbook["Answer key workbook"] --> Publisher["Publish or reuse dataset and templates"]
    Prompts["App prompt templates"] --> Publisher
    Publisher --> Hub["Arize AX Prompt Hub"]
    Publisher --> Dataset["Arize AX dataset with design IDs and labels"]
    Dataset -->|"When a benchmark is requested"| SDK["Arize AX experiment runner"]
    Docs["Local sample designs and Word standards"] --> Review["Extract evidence with OpenAI and assess gaps"]
    SDK --> Review
    Review --> Score["Score gaps, risk, coverage, and citations locally"]
    Score --> Reports["Save dashboard scores"]
    Reports --> Upload["Create experiment with dataset example IDs and outputs"]
    Upload --> Annotate["Attach numeric scores by Arize run ID"]
    Annotate --> AX["Per-design experiment results in Arize AX"]
```

## Performance dashboard

Startup publication and dashboard actions save the latest result for each check. The browser polls for updates during startup publication and while an action runs. [Backend reporting setup](backend/README.md#performance-dashboard)

```mermaid
flowchart LR
    Benchmark["Publish assets and run Arize AX benchmark"] --> Reports["Latest JSON summaries"]
    Startup["Publish full dataset and Prompt Hub templates at startup"] --> Reports
    Publish["Publish full dataset and Prompt Hub templates on demand"] --> Reports
    Validate["Successful benchmark fixture validation"] --> Reports
    Tests["Backend test suite in a separate Python process"] --> Reports
    Dashboard["Performance page"] -->|"GET /api/performance"| API["FastAPI"]
    Dashboard -->|"Start a dashboard action with a token"| API
    API --> Benchmark
    API --> Publish
    API --> Tests
    API --> Validate
    Reports --> API
    API -->|"Saved result or report status"| Dashboard
```

## Report evaluation

The [evaluation CLI](backend/README.md#evaluate-an-exported-report) scores a report after it has been generated.

```mermaid
flowchart TD
    Record["Exported JSON record with a report"] --> Evaluate["Evaluation CLI"]
    Source["Original design document"] --> Evaluate
    Supporting["Original supporting documents, when cited"] --> Evaluate
    Key["Human answer key"] --> Evaluate
    Evaluate --> Rules["Load applicable rules using the recorded date and document type"]
    Rules --> Metrics["Score missing evidence, risk tier agreement, rule coverage, and citation validity"]
    Metrics --> Judge{"Optional OpenAI judge enabled?"}
    Judge -->|"Yes"| OpenAI["Score clarity, actionability, and hallucination risk"]
    Judge -->|"No"| Output["Print JSON scores"]
    OpenAI --> Output

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Record,Source,Supporting,Key user;
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
