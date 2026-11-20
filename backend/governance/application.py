from asyncio import CancelledError, create_task
from contextlib import asynccontextmanager, suppress
from logging import getLogger
from os import getenv
from threading import Lock

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from starlette.concurrency import run_in_threadpool

from .agent.graph import compile_workflow
from .api import document_reviews, performance, sample_reviews, standards_import
from .api.tracing import configure_arize
from .evaluation.publish import ArizePublicationError, arize_api_key, publish_bundled_assets

logger = getLogger(__name__)


async def publish_startup_assets(app: FastAPI, space: str, api_key: str):
    try:
        summary = await run_in_threadpool(publish_bundled_assets, space, api_key)
    except ArizePublicationError as exc:
        app.state.arize_publication = {"status": "failed", "message": str(exc)}
        logger.warning("Arize startup publication failed during %s (%s, status %s).", exc.phase, exc.error_type, exc.status)
    except Exception as exc:
        app.state.arize_publication = {
            "status": "failed",
            "message": "Startup publication failed. Check the backend logs and Arize settings.",
        }
        status = getattr(exc, "status", getattr(exc, "status_code", None))
        logger.warning("Arize startup publication failed (%s, status %s).", type(exc).__name__, status)
    else:
        app.state.arize_publication = {"status": "complete"}
        logger.info("Arize startup publication registered dataset %s and %d prompts.",
                    summary["dataset_id"], len(summary["prompts"]))


@asynccontextmanager
async def lifespan(app: FastAPI):
    tracer_provider = configure_arize()
    publication = None
    try:
        app.state.tracer = (
            tracer_provider.get_tracer("archgovasst") if tracer_provider else None
        )
        checkpointer = InMemorySaver()
        app.state.checkpointer = checkpointer
        app.state.workflow = compile_workflow(checkpointer)
        app.state.decision_lock = Lock()
        space = getenv("ARIZE_SPACE_ID", "").strip()
        api_key = arize_api_key()
        app.state.arize_publication = {"status": "unconfigured"}
        if space and api_key:
            app.state.arize_publication = {"status": "running"}
            publication = create_task(publish_startup_assets(app, space, api_key))
        yield
    finally:
        if publication is not None:
            publication.cancel()
            with suppress(CancelledError):
                await publication
        if tracer_provider is not None:
            await run_in_threadpool(tracer_provider.shutdown)


app = FastAPI(title="Architecture Governance Assistant", lifespan=lifespan)
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware, allow_origins=allowed_origins, allow_methods=["GET", "POST"], allow_headers=["Authorization"]
)
app.include_router(sample_reviews.router)
app.include_router(document_reviews.router)
app.include_router(standards_import.router)
app.include_router(performance.router)


@app.middleware("http")
async def prevent_review_caching(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/reviews"):
        response.headers["Cache-Control"] = "no-store"
    return response
