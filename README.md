# Architecture Governance Assistant

Architecture Governance Assistant reviews design documents against versioned governance standards. OpenAI extracts cited evidence, LangGraph pauses for two human decisions, and a deterministic policy check produces findings and a risk tier.

## Project components

- The React and Vite frontend uploads documents and presents the evidence and report checkpoints. [Frontend setup, configuration, and build guide](frontend/README.md)
- The Python and FastAPI backend runs the LangGraph workflow, retrieves approved rules from Chroma, and holds review checkpoints in memory until the backend restarts. [Backend setup, API, and Railway deployment guide](backend/README.md)

## Try it locally

Start the backend on port 8000, then start the frontend in a separate terminal using the guides above. Open the URL printed by Vite. To run a document review, configure the backend's `OPENAI_API_KEY` and Chroma connection, then import the [Word standards](backend/standards/README.md). The [sample review API](#sample-review) returns fictional findings without those services.

For the full list of project commands, see the [command reference](COMMANDS.md).

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
