# Architecture Governance Assistant Backend

The FastAPI service provides fictional architecture reviews for the [React frontend](../frontend/README.md).

## Code layout

- [`main.py`](main.py) exposes the Uvicorn entry point.
- [`governance/application.py`](governance/application.py) configures FastAPI, CORS, and startup and shutdown.
- [`governance/reviews.py`](governance/reviews.py) defines the sample review route and response models.
- [`governance/health.py`](governance/health.py) defines the Chroma health check.
- [`governance/chroma.py`](governance/chroma.py) and [`governance/tracing.py`](governance/tracing.py) configure the Chroma client and Arize tracing.

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

## Deploy on Railway

Set the Railway service root to `/backend` and use this start command. Railway provides `PORT`.

```sh
uvicorn main:app --host 0.0.0.0 --port "$PORT"
```

Generate a public HTTPS domain under Networking. In the service's Variables tab, set `CORS_ALLOWED_ORIGINS` to the exact browser origins that call the backend directly, separated by commas. For example, use `https://your-frontend.example.com,http://localhost:5173` to allow both a hosted frontend and local Vite. The local Vite proxy works with the default empty setting. Use [`.env.example`](.env.example) as a reference for the value.

## Connect Arize AX and Chroma

Set these variables on the **FastAPI service** in Railway and redeploy. For local development, set them in the shell that starts Uvicorn. [`.env.example`](.env.example) lists the variable names. Both integrations are optional.

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

Use Railway's variable autocomplete to select the actual Chroma service, or paste its private hostname from **Settings → Networking**. The backend builds the private HTTP URL from these values. Clear `CHROMA_URL` and `CHROMA_API_KEY` when switching to `CHROMA_PRIVATE_HOST`. The backend creates the Chroma client at startup, so an unreachable server can prevent startup. See [Railway private domains](https://docs.railway.com/networking/domains/working-with-domains#private-domains).

Use `GET /api/health/chroma` in the FastAPI docs to verify database access. It returns `connected` on a successful read and `disabled` if Chroma is unconfigured. A read failure after startup returns HTTP 503. The sample review continues to generate fictional findings in memory.

Call `GET /api/reviews/sample` and look for the `generate_sample_review` span in the Arize project. The span records timing and status. The trace does not include the response body or request headers. See [Arize AX tracing setup](https://arize.com/docs/ax/observe/tracing/setup/manual-instrumentation) and the [Chroma client reference](https://docs.trychroma.com/reference/python/client).

See [COMMANDS.md](../COMMANDS.md) for the project command reference.
