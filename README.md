# Architecture Governance Assistant

Architecture Governance Assistant demonstrates how an architecture review for an AI system can present findings and next steps across security and privacy, architecture fit, and operational readiness. The app uses fictional reviews to show what the output looks like.

## Project components

- The React and Vite frontend displays the review and lets users load a sample. [Frontend setup, configuration, and build guide](frontend/README.md)
- The Python and FastAPI backend serves sample reviews as JSON at `GET /api/reviews/sample`. [Backend setup, API, and Railway deployment guide](backend/README.md)

## Try it locally

Start the backend on port 8000, then start the frontend in a separate terminal using the guides above. Open the URL printed by Vite and select **Load sample review**. Vite forwards the request to the local backend.

For the full list of project commands, see the [command reference](COMMANDS.md).
