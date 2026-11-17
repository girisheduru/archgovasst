# Architecture Governance Assistant Backend

FastAPI serves a LangGraph document review workflow for the [React frontend](../frontend/README.md) and a fictional sample endpoint for API checks.

## Code layout

| Architecture layer | Code |
| --- | --- |
| Web UI and API | The [React frontend](../frontend/README.md) calls the [FastAPI routes](governance/api/). [`main.py`](main.py) exposes the app, and [`application.py`](governance/application.py) configures CORS and initializes the in-memory checkpointer. |
| Governance agent | [`graph.py`](governance/agent/graph.py) defines LangGraph sequencing and both approval checkpoints. [`documents.py`](governance/agent/documents.py) parses uploads, [`evidence.py`](governance/agent/evidence.py) validates model citations using the instructions in [`prompts.py`](governance/agent/prompts.py), and [`policy.py`](governance/agent/policy.py) calculates findings and risk. |
| LLM provider | [`providers/openai.py`](governance/providers/openai.py) handles OpenAI embeddings and structured responses. |
| Chroma standards store | [`ingestion.py`](governance/standards_store/ingestion.py) embeds and imports rule versions, [`catalog.py`](governance/standards_store/catalog.py) resolves applicable versions, and [`chroma.py`](governance/standards_store/chroma.py) configures the connection. |
| Evaluation | [`metrics.py`](governance/evaluation/metrics.py) scores the report against the source and answer key, and [`judge.py`](governance/evaluation/judge.py) runs the optional LLM evaluation. |
| Source documents | [`backend/standards/`](standards/) contains the four Word standards used for import. |

[`governance/standards.py`](governance/standards.py) and [`governance/evaluate.py`](governance/evaluate.py) are the command-line entry points for standards import and evaluation.

## Run locally

Use Python 3.11 or newer. From the repository root, create a virtual environment, install the dependencies, and start the server.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m uvicorn backend.main:app --reload
```

The server listens at `http://127.0.0.1:8000`. Open the [interactive API docs](http://127.0.0.1:8000/docs), or try the endpoint from another terminal.

```sh
curl http://127.0.0.1:8000/api/reviews/sample
```

## Sample review API

`GET /api/reviews/sample` returns `sample: true`, a fictional `system_name`, and a `review_areas` list. Each area contains a `title`, `finding`, and `next_step`. The service selects a system name and findings on each request and sends `Cache-Control: no-store`.

## Configure document reviews

### Upload approved standards from the frontend

Set `STANDARDS_IMPORT_TOKEN` to a strong secret in the backend process environment or Railway service variables, then restart or redeploy. Share it only with standards maintainers. The `/standards` form sends the entered token as a bearer credential to `POST /api/standards/import`. An empty backend value disables this endpoint.

The form accepts up to 10 approved Word (.docx) standards, each up to 10 MB and 20 MB combined, with at most 200 rules per import. The backend extracts rule IDs, statements, evidence guidance, and effective dates directly from the documents. Use the [bundled Word template format](standards/README.md).

Both the form and CLI overwrite any stored rule with a matching ID and effective date, including its metadata and embedding. A different effective date creates a separate version. On success the API returns `added` and `updated` counts. It returns HTTP 422 if a rule ID and effective date appear more than once in the upload, and HTTP 503 if embedding or storage fails.

If the upload says OpenAI rejected the backend credentials, set a valid `OPENAI_API_KEY` on the FastAPI service, then redeploy and retry the upload. Locally, set the key in the shell that starts Uvicorn and restart the backend. The import fails before writing rule versions to Chroma.

### Configure the standards store

Set `OPENAI_API_KEY` in the backend shell or Railway service variables. The runtime reads process environment variables. Use [`.env.example`](.env.example) as a reference. Document reviews default to `gpt-6.1-luna` when `OPENAI_MODEL` is unset. Set `OPENAI_MODEL` to override the default with a model that supports Structured Outputs and is available to your API project. Set a Chroma connection using the options below. `CHROMA_STANDARDS_COLLECTION` defaults to `governance-standards`.

From the clone root with the backend dependencies, OpenAI key, and Chroma connection configured, import the four bundled Word standards. Both import paths create one Chroma record per rule version and send the rule text and evidence guidance to OpenAI's `text-embedding-3-small` for embedding.

```sh
.venv/bin/python -m backend.governance.standards backend/standards/STD-*.docx
```

For each rule ID, the review selects the latest version effective on or before the review date. It then checks every rule applicable to the selected document type. OpenAI extracts candidate quotes using a structured schema. The backend validates each quote against the normalized text of the cited PDF page or Word body block. The reviewer confirms the extraction before the policy engine produces findings. The assessed tier is the highest of the declared tier and the configured risks of rules with missing evidence. A second reviewer decision finalizes the report.

## Document review API

- `POST /api/reviews` accepts multipart fields `document` (PDF or DOCX), `document_type`, `declared_tier` (`low`, `medium`, or `high`), and optional `as_of` (ISO date, defaults to the server date). The response includes a review ID, the pending evidence checkpoint, and the retrieved rule text, standard ID, and effective date for each evidence item.
- `GET /api/reviews/{review_id}` returns the current checkpoint, extraction, report, and decision history.
- `POST /api/reviews/{review_id}/decision` accepts JSON with `checkpoint` (`confirm_evidence` or `approve_report`), `decision` (`approve` or `reject`), `reviewer`, and optional `note`. A decision for an earlier checkpoint returns HTTP 409. Rejection at either checkpoint ends that review.

PDFs need selectable text and must be unencrypted, with up to 100 pages. Uploads are limited to 10 MB and 160,000 extracted characters. Word review reads body paragraphs and tables. Diagrams and images need a text description in the document.

LangGraph keeps extracted document text, the standards snapshot, and decisions in process memory between requests. A backend restart clears all reviews. Run one worker and one replica so each approval reaches the process that started the review. Keep live review routes behind your authenticated gateway or on a private network. Review IDs grant access to the associated state and decisions, and reviewer names are self-reported.

## Evaluate an exported report

Download the JSON decision record after the report has been generated. Supply the original document and a human answer key with `not_evidenced_rule_ids` (a list of rule IDs) and `risk_tier`.

```sh
.venv/bin/python -m backend.governance.evaluate /path/to/review.json /path/to/design.pdf /path/to/answer-key.json
```

The evaluator reports gap precision and recall, risk tier agreement, rule coverage, and citation validity. Append `--judge` to send the report, answer key, and extracted document text to OpenAI for clarity, actionability, and hallucination-risk scores. Evaluations leave the review and its decisions untouched.

## Deploy on Railway

Set the Railway service root to `/backend` and use this start command. Railway provides `PORT`.

```sh
uvicorn main:app --host 0.0.0.0 --port "$PORT"
```

For the sample API, you can generate a public HTTPS domain under Networking. For document reviews, route requests through your authenticated gateway. In the service's Variables tab, set `CORS_ALLOWED_ORIGINS` to the exact browser origins that call the backend directly, separated by commas. For example, use `https://your-frontend.example.com,http://localhost:5173` to allow both a hosted frontend and local Vite. The local Vite proxy works with the default empty setting. Use [`.env.example`](.env.example) as a reference for the value.

## Connect Arize AX and Chroma

Set these variables on the **FastAPI service** in Railway and redeploy. For local development, set them in the shell that starts Uvicorn. [`.env.example`](.env.example) lists the variable names. Arize is optional. Chroma is required for document reviews.

| Integration | Variable | Value |
| --- | --- | --- |
| Arize AX | `ARIZE_SPACE_ID` | Space ID from Arize AX Settings → API Keys |
| Arize AX | `ARIZE_API_KEY` | API key for that space |
| Arize AX | `ARIZE_PROJECT_NAME` | Trace project name. Defaults to `archgovasst`. |
| Arize AX | `ARIZE_COLLECTOR_ENDPOINT` | Optional collector endpoint for your Arize deployment |
| Chroma Cloud | `CHROMA_API_KEY` | Chroma Cloud API key |
| Chroma Cloud | `CHROMA_TENANT` | Tenant ID for the database |
| Chroma Cloud | `CHROMA_DATABASE` | Name of an existing database |
| Chroma on Railway | `CHROMA_PRIVATE_HOST` | Private hostname of the Chroma service in the same Railway environment |
| Chroma on Railway | `CHROMA_PORT` | Port the Chroma service listens on. Defaults to `8000`. |
| Custom Chroma endpoint | `CHROMA_URL` | Full server URL for existing deployments or local development |
| Self-hosted Chroma | `CHROMA_TENANT`, `CHROMA_DATABASE` | Optional overrides for `default_tenant` and `default_database` |

For Chroma hosted in the same Railway project and environment, set the private hostname and listening port under **FastAPI service → Variables**. For a service named `Chroma` listening on port `8000`, use:

```dotenv
CHROMA_PRIVATE_HOST=${{Chroma.RAILWAY_PRIVATE_DOMAIN}}
CHROMA_PORT=8000
```

Use Railway's variable autocomplete to select the actual Chroma service, or paste its private hostname from **Settings → Networking**. The backend builds the private HTTP URL from these values. Clear `CHROMA_URL` and `CHROMA_API_KEY` when switching to `CHROMA_PRIVATE_HOST`. See [Railway private domains](https://docs.railway.com/networking/domains/working-with-domains#private-domains).

Keep the Chroma service on Railway's private network. FastAPI startup and sample reviews run independently of Chroma.

If a standards upload returns HTTP 503 with `Could not import standards`, search the FastAPI deployment logs for `Standards import failed`. The entry identifies the failed step and exception type, including the underlying exception type when available. For a Chroma connection failure, compare `CHROMA_PORT` with the port in the Chroma service startup logs. The FastAPI listening port belongs to a separate service.

If a document review reports `Could not read the approved standards collection.`, check the FastAPI deployment logs for `Standards read failed`. The entry gives the failed step and exception type. For a connection failure, check the private hostname, listening port, and Chroma deployment. If opening the collection fails because it is missing, confirm `CHROMA_STANDARDS_COLLECTION` and [import the approved standards](#upload-approved-standards-from-the-frontend) into that instance.

Call `GET /api/reviews/sample` and look for the `generate_sample_review` span in the Arize project. The span records timing and status. The trace does not include the response body or request headers. See [Arize AX tracing setup](https://arize.com/docs/ax/observe/tracing/setup/manual-instrumentation) and the [Chroma client reference](https://docs.trychroma.com/reference/python/client).

See [COMMANDS.md](../COMMANDS.md) for the project command reference.
