# Architecture Governance Assistant Backend

FastAPI serves a LangGraph document review workflow for the [React frontend](../frontend/README.md) and a fictional sample endpoint for API checks.

## Code layout

| Architecture layer | Code |
| --- | --- |
| Web UI and API | The [React frontend](../frontend/README.md) calls the [FastAPI routes](governance/api/). [`main.py`](main.py) exposes the app, and [`application.py`](governance/application.py) configures CORS and initializes the in-memory checkpointer. |
| Governance agent | [`graph.py`](governance/agent/graph.py) defines LangGraph sequencing and both approval checkpoints. [`documents.py`](governance/agent/documents.py) parses uploads, [`retrieval.py`](governance/agent/retrieval.py) ranks design passages for each applicable rule, [`evidence.py`](governance/agent/evidence.py) extracts and verifies citations, and [`policy.py`](governance/agent/policy.py) calculates findings and risk. |
| LLM provider | [`providers/openai.py`](governance/providers/openai.py) handles OpenAI embeddings and structured responses. |
| Chroma standards store | [`ingestion.py`](governance/standards_store/ingestion.py) embeds and imports rule versions, [`catalog.py`](governance/standards_store/catalog.py) resolves applicable versions, and [`chroma.py`](governance/standards_store/chroma.py) configures the connection. |
| Evaluation | [`dataset.py`](governance/evaluation/dataset.py) loads the workbook and Word fixtures. [`experiment.py`](governance/evaluation/experiment.py) runs the Arize benchmark using [`metrics.py`](governance/evaluation/metrics.py). [`judge.py`](governance/evaluation/judge.py) provides optional LLM scoring for exported reports. |
| Source documents | [`datadocs/`](datadocs/) contains the Word standards, solution designs, and answer workbook. |

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

Set `STANDARDS_IMPORT_TOKEN` to a strong secret in the backend process environment or Railway service variables, then restart or redeploy. Share it only with standards maintainers. The `/standards` form sends the entered token as a bearer credential for import and reset requests. An empty backend value disables both endpoints.

The form accepts up to 10 approved Word (.docx) standards, each up to 10 MB and 20 MB combined, with at most 200 rules per import. The backend extracts rule IDs, statements, evidence guidance, and effective dates directly from the documents. Use the [bundled Word template format](datadocs/README.md).

Both the form and CLI overwrite any stored rule with a matching ID and effective date, including its metadata and embedding. A different effective date creates a separate version. On success `POST /api/standards/import` returns `added` and `updated` counts. It returns HTTP 422 if a rule ID and effective date appear more than once in the upload, and HTTP 503 if embedding or storage fails.

If the upload says OpenAI rejected the backend credentials, set a valid `OPENAI_API_KEY` on the FastAPI service, then redeploy and retry the upload. Locally, set the key in the shell that starts Uvicorn and restart the backend. The import fails before writing rule versions to Chroma.

After the maintainer confirms the reset in the browser, `POST /api/standards/clear` deletes the configured Chroma standards collection, including all rule versions and embeddings. It returns `{"cleared": true}` after deletion, `{"cleared": false}` if the collection is already absent, and HTTP 503 if Chroma cannot complete the request. The next import recreates the collection.

### Configure the standards store

Set `OPENAI_API_KEY` in the backend shell or Railway service variables. The runtime reads process environment variables. Use [`.env.example`](.env.example) as a reference. Document reviews and optional LLM evaluation default to `gpt-6-luna` when `OPENAI_MODEL` is unset. Set `OPENAI_MODEL` to override the default with a model that supports Structured Outputs and is available to your API project. If your backend still sets `OPENAI_MODEL=gpt-6.1-luna`, change it to `gpt-6-luna` and restart Uvicorn or redeploy the Railway service before retrying the review. Set a Chroma connection using the options below. `CHROMA_STANDARDS_COLLECTION` defaults to `governance-standards`.

From the clone root with the backend dependencies, OpenAI key, and Chroma connection configured, import the four bundled Word standards. Both import paths create one Chroma record per rule version and send the rule text and evidence guidance to OpenAI's `text-embedding-3-small` for embedding.

```sh
.venv/bin/python -m backend.governance.standards backend/datadocs/standards/STD-*.docx
```

### Retrieve evidence from the uploaded design

For each rule ID, the review selects the latest version effective on or before the review date, then keeps every rule applicable to the selected document type. The extraction step groups short source sections into passages and splits long sections with overlap, preserving PDF page and Word body block labels.

The backend embeds the passages and rule queries with OpenAI, then combines keyword and semantic rankings to select up to three passages per rule. OpenAI extracts structured candidate quotes. The backend verifies each quote against the passages supplied for that rule and retries rules without a verified quote against the full design. It goes directly to the full design when there are at most three passages or when ranking fails. Uploaded design passages and embeddings are used within the review request. The Chroma collection stores approved standards.

The reviewer confirms the extraction before the policy engine produces findings. The assessed tier is the highest of the declared tier and the configured risks of rules with missing evidence. A second reviewer decision finalizes the report. See the [retrieval architecture](../ARCHITECTURE.md#rule-selection-and-evidence-retrieval).

For a rule without evidence, the reviewer can request guidance from OpenAI using the approved rule, evidence requirement, and up to three design passages. While evidence confirmation is pending, the reviewer can also upload a supporting document for that one rule. The backend verifies the returned quote against the supporting text and stages it for explicit inclusion in the evidence decision. The checkpoint stores the candidate quote, source label, filename, and file hash. The uploaded supporting file and its full text are used within the recheck request.

### Compare retrieval with the full-document baseline

With `EVIDENCE_RETRIEVAL_MODE` unset, the backend uses passage retrieval. Set `EVIDENCE_RETRIEVAL_MODE` to `full_document` and restart the backend to send all applicable rules and the whole parsed design in a single extraction request.

Run the [Arize AX benchmark](#run-the-arize-ax-benchmark) in each mode with the same cases and OpenAI model. Configure `EVIDENCE_RETRIEVAL_MODE` in the shell that starts each benchmark. Arize reuses the dataset for the same design files, labels, and rules, and the CLI gives each run a distinct name by default. For a comparison of live reviews, export the two reports and [score each against the same human answer key](#evaluate-an-exported-report). Compare upload trace duration, Responses tokens across extraction passes, and embedding tokens.

## Document review API

- `POST /api/reviews` accepts multipart fields `document` (PDF or DOCX), `document_type`, `declared_tier` (`low`, `medium`, or `high`), and optional `as_of` (ISO date, defaults to the server date). The response includes a review ID, the pending evidence checkpoint, and the retrieved rule text, standard ID, and effective date for each evidence item.
- `GET /api/reviews/{review_id}` returns the current checkpoint, extraction, report, and decision history.
- `POST /api/reviews/{review_id}/gap-guidance` accepts form field `rule_id` for a rule without evidence and returns `missing_evidence` and `next_step`.
- `POST /api/reviews/{review_id}/supporting-evidence` accepts multipart fields `rule_id` and `document` (PDF or DOCX) at the `confirm_evidence` checkpoint. It returns the updated review with a `supporting_candidate` on the rule's extraction row when a quote is verified. An unsuccessful search leaves any previously verified candidate in place.
- `POST /api/reviews/{review_id}/decision` accepts JSON with `checkpoint` (`confirm_evidence` or `approve_report`), `decision` (`approve` or `reject`), `reviewer`, optional `note`, and optional `comments` keyed by rule ID. Each comment must contain 1 to 2,000 characters after trimming and refer to a rule shown at that checkpoint. Comments are stored on the decision in `audit` and printed with the corresponding rule in the final PDF. When approving evidence, pass optional `supporting_evidence` mapping rule IDs to the selected candidate IDs. A decision with an outdated candidate or checkpoint returns HTTP 409. Rejection at either checkpoint ends that review.
- `GET /api/reviews/{review_id}/report.pdf` downloads the final report as a PDF after a decision at the report checkpoint. It returns HTTP 409 until a final report is available, including when the review stopped at evidence confirmation.

PDFs need selectable text and must be unencrypted, with up to 100 pages. Uploads are limited to 10 MB and 160,000 extracted characters. Word review reads body paragraphs and tables. Diagrams and images need a text description in the document.

LangGraph keeps extracted document text, the standards snapshot, and decisions in process memory between requests. A backend restart clears all reviews. Run one worker and one replica so each approval reaches the process that started the review. Keep live review routes behind your authenticated gateway or on a private network. Review IDs grant access to the associated state and decisions, and reviewer names are self-reported.

## Run the Arize AX benchmark

From the clone root, install the backend requirements, which include the evaluation dependencies, then validate the fixtures:

```sh
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m backend.governance.evaluate --validate-only
```

Set `ARIZE_SPACE_ID` for the destination Arize AX space and use a key authorized to manage prompts, datasets, and experiments there. Set that key as `ARIZE_EVAL_API_KEY` or use `ARIZE_API_KEY` for both evaluation and tracing. Set `OPENAI_API_KEY` for evidence extraction. The CLI uses the local Word standards and can run independently of the web app and Chroma. [Arize API key permissions](https://arize.com/docs/ax/security-and-settings/api-keys)

```sh
.venv/bin/python -m backend.governance.evaluate --case SD-01
.venv/bin/python -m backend.governance.evaluate
```

The first command runs one design. The second runs all 24. Both publish or reuse the selected dataset and four Prompt Hub templates, then run the app's extraction and gap assessment and save a per-design experiment in Arize AX. The CLI prints the space, dataset, prompt version, and experiment IDs and mean scores. In the same Arize space, look for the templates in Prompt Hub and the experiment under its dataset. Arize receives prompt templates, design IDs, expected and predicted rule IDs, risk and outcome labels, and scores. The extraction step sends bundled design text and rules to OpenAI.

The benchmark treats all 75 rows in the workbook's **Expected findings** sheet as evidence gaps, including planted contradictions and missing sections. It maps business criticality tiers 1, 2, and 3 to high, medium, and low declared risk, and derives the expected assessed tier from the declared tier and labeled gaps. Suggested approval outcomes remain reference labels. The benchmark scores the automated assessment before the human approval steps.

In Arize AX, inspect missed and unexpected rule IDs for each design. Compare gap precision, recall, exact gap-set match, risk tier agreement, rule coverage, and citation validity. Undefined precision or recall and cases without citations are excluded from the respective means. Citation validity checks that quotes appear in the cited source. The workbook labels measure whether the app identified insufficient evidence.

## Performance dashboard

Install the backend requirements and set a private `PERFORMANCE_RUN_TOKEN` on the backend. On **Performance**, enter the token once and select an action. Ready buttons accept a click and prompt for the token if the field is empty.

| Dashboard action | API endpoint | Requirements |
| --- | --- | --- |
| **Run AI benchmark** | `POST /api/performance/benchmark?scope=smoke` or `scope=full` | OpenAI key, Arize publishing credentials, and evaluation dependencies. |
| **Publish Arize assets** | `POST /api/performance/publish` | Arize publishing credentials and evaluation dependencies. Publishes the full dataset and Prompt Hub templates. |
| **Run application tests** | `POST /api/performance/tests` | Backend dependencies and `httpx`. The suite runs in an isolated Python process and saves pass or fail counts. |
| **Validate benchmark fixtures** | `POST /api/performance/fixtures` | The Excel reader from the backend requirements. Validates the full bundle and saves fixture counts. |

Set `ARIZE_SPACE_ID` and either `ARIZE_EVAL_API_KEY` or `ARIZE_API_KEY` for publication and benchmarks. The same settings enable startup publication. Both local checks can run without Arize or OpenAI configuration.

On Railway, set the credentials and run token under **FastAPI service → Variables** in the environment that serves your dashboard, then apply the staged changes. FastAPI reads those variables directly at runtime. If the values are shared across services, add the references to the FastAPI service. Set only the public backend URL in the frontend's `VITE_API_BASE_URL` when frontend and API use separate origins. [Railway variables](https://docs.railway.com/variables)

Expand **Backend configuration** on the Performance page to see which settings the connected backend received. The check shows presence only. If the page cannot reach the API, check the frontend URL and CORS guidance displayed on the page.

Each action uses bearer-token authentication. The backend accepts one dashboard action per process at a time. Publishing and benchmarking wait for startup publication to finish. Run the dashboard backend with a single worker and replica so polling and controls share one job state. A process restart ends the in-flight job. Completed reports and IDs saved before a failure remain visible. The page polls `GET /api/performance` while an action or startup publication runs. The response includes per-action availability, `job` and `arize_publication` statuses, and entries for `assets`, `benchmark`, `tests`, and `fixtures`. Each report entry is `pending` before its first report, `available` with a `report` when saved, or `unavailable` if it cannot be read.

Reports are saved in the ignored `.performance/` directory at the clone root by default, or in the backend directory when deployed by itself. Set `PERFORMANCE_REPORT_DIR` to a shared absolute directory for the backend and any separate CLI or CI jobs. On a hosted backend, use a persistent volume or deploy the report files with the service. The API exposes summaries to anyone who can access it. Reports contain benchmark IDs, scores, and test outcomes. They exclude credentials, design text, extracted quotes, and test tracebacks.

On Railway with `/backend` as the service root, redeploy with the updated `requirements.txt` and configured backend variables.

## Publish the dataset and prompts

When the backend starts with Arize credentials, it publishes or reuses the full benchmark dataset and four Prompt Hub templates in the background. The dashboard displays progress and records publication IDs. A publishing error appears in the dashboard and backend logs while the application continues serving requests. Startup uses the bundled design IDs, answer labels, and prompt templates. OpenAI calls and experiment creation occur when a benchmark is run.

To publish the same assets outside the running application, run the publisher from the clone root with the evaluation dependencies installed. The environment file supplies `ARIZE_SPACE_ID` and either `ARIZE_EVAL_API_KEY` or `ARIZE_API_KEY`. It can also set `OPENAI_MODEL` for the Prompt Hub entries. Omit `--env-file` to use the current shell environment.

```sh
.venv/bin/python -m backend.governance.evaluation.publish --env-file /path/to/.env
```

The command publishes the benchmark dataset, full-document evidence extraction, passage evidence extraction, gap guidance, and the optional review judge. It prints the dataset, prompt, and version IDs. Reruns reuse the same dataset and latest matching prompt versions. The dataset contains design IDs and answer labels. The benchmark reads the design text from the local Word files.

Use the `payload` variable in Prompt Hub to pass the JSON input for a template. The extraction prompts accept `rules` and either `document` or `passages`. The guidance prompt accepts `rule` and `design_passages`. The judge accepts `findings`, `risk_tier`, `answer_key`, and `source`. The local export includes the response schemas the app applies when it calls OpenAI.

```sh
.venv/bin/python -m backend.governance.evaluation.publish --export arize-governance.json
```

## Evaluate an exported report

Download the JSON decision record after the report has been generated. Supply the original document and a human answer key with `not_evidenced_rule_ids` (a list of rule IDs) and `risk_tier`.

```sh
.venv/bin/python -m backend.governance.evaluate /path/to/review.json /path/to/design.pdf /path/to/answer-key.json
```

The evaluator reports gap precision and recall, risk tier agreement, rule coverage, and citation validity. Append `--judge` to send the report, answer key, and extracted document text to OpenAI for clarity, actionability, and hallucination-risk scores. Evaluations leave the review and its decisions untouched.

For a review with confirmed supporting evidence, pass each original supporting file with `--supporting-document PATH` and prepare the answer key using those documents as well as the design. The evaluator matches files by SHA-256 and counts citations whose files are unavailable as unverified. With `--judge`, supplied supporting text is included in the judging request.

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
| Arize AX | `ARIZE_EVAL_API_KEY` | Optional key for publishing datasets, prompts, and experiments. Defaults to using `ARIZE_API_KEY`. |
| Arize AX | `ARIZE_PROJECT_NAME` | Trace project name. Defaults to `archgovasst`. |
| Arize AX | `ARIZE_COLLECTOR_ENDPOINT` | Optional collector endpoint for your Arize deployment |
| Performance | `PERFORMANCE_RUN_TOKEN` | Private token for starting dashboard actions. |
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

Call `GET /api/reviews/sample` and look for the `generate_sample_review` span in the Arize project. For an uploaded document, look for `start_document_review`, then `confirm_evidence` and `approve_report` as you submit checkpoint decisions. These operations run in separate requests. Use the Arize Sessions view with the review ID to group their spans. Expand each request trace to see the LangGraph nodes (`retrieve_applicable_rules`, `extract_evidence_with_llm`, `confirm_evidence`, `assess_evidence_gaps`, `mark_report_ready`, and `approve_report`) that ran during that request. In the upload trace, `chroma.load_rules` is under `retrieve_applicable_rules`. Under `extract_evidence_with_llm`, look for `design.rank_passages` and its embedding call when passage retrieval runs, `openai.responses.parse` for quote extraction, and `design.search_full_document` when the full design is checked. Human checkpoint pauses are successful waits, marked with `review.waiting_for_decision`. When a decision resumes a checkpoint, the request span contains a child node span with the same name.

Document review spans record timing, operation status, the review ID, section and rule counts, and the model name and token usage returned by OpenAI. They exclude document contents, model prompts and responses, reviewer details, and exception messages. See [Arize AX tracing setup](https://arize.com/docs/ax/observe/tracing/setup/manual-instrumentation).

See [COMMANDS.md](../COMMANDS.md) for the project command reference.
