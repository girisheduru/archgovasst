# AI Architecture Governance Assistant

Architecture policies often exist in scattered artifacts. Development teams don’t always know which policies apply to their proposed solution, while architects manually review solution design documents. Important questions around encryption, identity, networking, secrets, observability, and resiliency can be overlooked, and reviews can be inconsistent.

AI Architecture Governance Assistant brings approved standards together and reviews design documents against every applicable, versioned governance rule. It searches relevant design passages first and checks the full design for rules without a verified quote. LangGraph pauses for two human decisions, and a deterministic policy check produces findings and a risk tier.

## Project components

- The React and Vite frontend uploads documents and presents the evidence and report checkpoints. [Frontend setup, configuration, and build guide](frontend/README.md)
- The Python and FastAPI backend runs the LangGraph workflow, retrieves approved rules from Chroma, and holds review checkpoints in memory until the backend restarts. [Backend setup, API, and Railway deployment guide](backend/README.md)

## Try it locally

Start the backend on port 8000, then start the frontend in a separate terminal using the guides above. Open the URL printed by Vite. To run a document review, configure the backend's `OPENAI_API_KEY` and Chroma connection, then import the [Word standards](backend/datadocs/README.md). The [sample review API](flowdiagrams.md#sample-review) returns fictional findings without those services.

With Arize configured, the backend publishes or reuses the full bundled dataset, four Prompt Hub templates, and 11 Eval Hub evaluators on startup. Each prompt has its own evaluator. Select **Performance** to run the AI benchmark, publish Arize assets independently, run application tests, or validate the benchmark fixtures. The page shows progress and results. Document reviews appear under the configured Arize trace project. [Dashboard setup](backend/README.md#performance-dashboard)

For the full list of project commands, see the [command reference](COMMANDS.md).

## Architecture and workflows

| LangGraph node | Role |
| --- | --- |
| `retrieve_applicable_rules` | Retrieves applicable rules from Chroma for the document type and standards date. |
| `extract_evidence_with_llm` | Uses an LLM to extract evidence and verifies the quotes against the design. |
| `confirm_evidence` | Pauses for a reviewer to confirm or reject the evidence and include selected quotes from supporting documents. |
| `assess_evidence_gaps` | Records findings and calculates the assessed risk tier. |
| `mark_report_ready` | Moves the review to the report approval stage. |
| `approve_report` | Pauses for a reviewer to approve or reject the report. |

The [architecture diagram](ARCHITECTURE.md) shows where LangGraph fits in the system. The [retrieval architecture](ARCHITECTURE.md#rule-selection-and-evidence-retrieval) explains rule selection, passage search, and the full-design fallback. The [workflow diagrams](flowdiagrams.md#langgraph-nodes-and-edges) show the paths through both reviewer decisions.

For a worked example of importing versioned rules and finding evidence in a design, see [RAG upload and retrieval](docs/rag-upload-and-retrieval.md).
