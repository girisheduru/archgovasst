from contextlib import asynccontextmanager
from os import getenv
from threading import Lock

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from starlette.concurrency import run_in_threadpool

from .agent.graph import compile_workflow
from .api import document_reviews, performance, sample_reviews, standards_import
from .api.tracing import configure_arize


@asynccontextmanager
async def lifespan(app: FastAPI):
    tracer_provider = configure_arize()
    try:
        app.state.tracer = (
            tracer_provider.get_tracer("archgovasst") if tracer_provider else None
        )
        checkpointer = InMemorySaver()
        app.state.checkpointer = checkpointer
        app.state.workflow = compile_workflow(checkpointer)
        app.state.decision_lock = Lock()
        yield
    finally:
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
