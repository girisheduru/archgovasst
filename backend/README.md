# Architecture Governance Assistant Backend

The FastAPI service provides fictional architecture reviews for the [React frontend](../frontend/README.md).

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

See [COMMANDS.md](../COMMANDS.md) for the project command reference.
