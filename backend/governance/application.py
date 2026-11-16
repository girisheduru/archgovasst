from contextlib import asynccontextmanager
from os import getenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from . import reviews
from .tracing import configure_arize


@asynccontextmanager
async def lifespan(app: FastAPI):
    tracer_provider = configure_arize()
    try:
        app.state.tracer = (
            tracer_provider.get_tracer("archgovasst") if tracer_provider else None
        )
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
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["GET"])
app.include_router(reviews.router)
