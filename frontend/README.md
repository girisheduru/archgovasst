# Architecture Governance Assistant Frontend

The React and Vite app presents three architecture review areas. Select **Load sample review** to see fictional findings and next steps from the [FastAPI backend](../backend/README.md).

## Run locally

Use Node.js 20.19 or later on the 20.x line, or Node.js 22.12 or later. From the repository root, run the following commands and open the URL Vite prints.

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

Start the backend on port 8000 to load sample reviews. By default, the Vite development server forwards `/api` requests to `http://127.0.0.1:8000`.

## Connect to a hosted backend

Use [`.env.example`](.env.example) as a template for `frontend/.env.local` during local development. Set `VITE_API_BASE_URL` to the backend's public HTTPS origin, omitting `/api`, and restart Vite. The backend must allow the browser's exact frontend origin in `CORS_ALLOWED_ORIGINS`.

For a hosted frontend, set `VITE_API_BASE_URL` in the build environment before building. Vite includes this value in the browser bundle, so use a public URL. If you leave it blank, the app makes same-origin requests and your hosting setup needs to route `/api` to the backend.

## Build and preview

From the repository root, run the following commands. The build writes to `frontend/dist/`, and the preview command serves that build locally.

```sh
npm --prefix frontend run build
npm --prefix frontend run preview
```

See [COMMANDS.md](../COMMANDS.md) for the project command reference.
