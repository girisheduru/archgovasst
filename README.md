# Architecture Governance Assistant

Architecture Governance Assistant reviews design documents against versioned governance standards. OpenAI extracts cited evidence, LangGraph pauses for two human decisions, and a deterministic policy check produces findings and a risk tier.

## Project components

- The React and Vite frontend uploads documents and presents the evidence and report checkpoints. [Frontend setup, configuration, and build guide](frontend/README.md)
- The Python and FastAPI backend runs the LangGraph workflow, retrieves approved rules from Chroma, and holds review checkpoints in memory until the backend restarts. [Backend setup, API, and Railway deployment guide](backend/README.md)

## Try it locally

Start the backend on port 8000, then start the frontend in a separate terminal using the guides above. Open the URL printed by Vite. To run a document review, configure the backend's `OPENAI_API_KEY` and Chroma connection, then import the [standards catalog](backend/standards/README.md). **Load sample review** still shows fictional findings without those services.

For the full list of project commands, see the [command reference](COMMANDS.md).
