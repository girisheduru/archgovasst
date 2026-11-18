# AI Architecture Governance Assistant

Architecture policies often exist in scattered artifacts. Development teams don’t always know which policies apply to their proposed solution, while architects manually review solution design documents. Important questions around encryption, identity, networking, secrets, observability, and resiliency can be overlooked, and reviews can be inconsistent.

AI Architecture Governance Assistant brings approved standards together and reviews design documents against every applicable, versioned governance rule. It searches relevant design passages first and checks the full design for rules without a verified quote. LangGraph pauses for two human decisions, and a deterministic policy check produces findings and a risk tier.

## Project components

- The React and Vite frontend uploads documents and presents the evidence and report checkpoints. [Frontend setup, configuration, and build guide](frontend/README.md)
- The Python and FastAPI backend runs the LangGraph workflow, retrieves approved rules from Chroma, and holds review checkpoints in memory until the backend restarts. [Backend setup, API, and Railway deployment guide](backend/README.md)

## Try it locally

Start the backend on port 8000, then start the frontend in a separate terminal using the guides above. Open the URL printed by Vite. To run a document review, configure the backend's `OPENAI_API_KEY` and Chroma connection, then import the [Word standards](backend/standards/README.md). The [sample review API](flowdiagrams.md#sample-review) returns fictional findings without those services.

For the full list of project commands, see the [command reference](COMMANDS.md).

## Architecture and workflows

See the [retrieval architecture](ARCHITECTURE.md#rule-selection-and-evidence-retrieval) for rule selection, passage search, and the full-design fallback. The [workflow diagrams](flowdiagrams.md) show the LangGraph nodes, edges, and reviewer checkpoints.
