from hmac import compare_digest
from importlib.metadata import PackageNotFoundError, version
from logging import getLogger
from os import getenv
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..evaluate import fixture_summary, missing_benchmark_settings, run_benchmark
from ..evaluation.dataset import load_dataset
from ..performance import read_report, save_report

router = APIRouter(prefix="/api/performance", tags=["Performance"])
bearer = HTTPBearer(auto_error=False)
logger = getLogger(__name__)
job_lock = Lock()
job = {"status": "idle"}


def runner_unavailable():
    if not getenv("PERFORMANCE_RUN_TOKEN", "").strip():
        return "Set PERFORMANCE_RUN_TOKEN on the backend to enable dashboard benchmark runs."
    missing = missing_benchmark_settings()
    if missing:
        return f"Configure the backend settings: {', '.join(missing)}."
    try:
        version("arize")
        version("openpyxl")
    except PackageNotFoundError:
        return "Install backend/requirements-eval.txt in the backend environment."
    return None


def update_job(status: str, phase: str):
    with job_lock:
        job.update(status=status, phase=phase)


def run_job(scope: Literal["smoke", "full"]):
    try:
        cases, rules = load_dataset()
        available_case_count = len(cases)
        save_report("fixtures", {**fixture_summary(cases, rules), "available_case_count": available_case_count})
        if scope == "smoke":
            case_id = min(cases)
            cases = {case_id: cases[case_id]}
        run_benchmark(cases, rules, available_case_count, on_phase=lambda phase: update_job("running", phase))
    except Exception as exc:
        phase = job["phase"]
        status = getattr(exc, "status", getattr(exc, "status_code", None))
        logger.error("Performance benchmark failed during %s (%s, status %s).", phase, type(exc).__name__, status)
        update_job("failed", phase)
    else:
        update_job("complete", "Benchmark finished")


@router.get("")
def get_performance(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    with job_lock:
        current_job = dict(job)
    return {
        "assets": read_report("assets"),
        "benchmark": read_report("benchmark"),
        "fixtures": read_report("fixtures"),
        "tests": read_report("tests"),
        "job": current_job,
        "arize_publication": getattr(request.app.state, "arize_publication", None),
        "runner_unavailable": runner_unavailable(),
    }


@router.post("/benchmark", status_code=202)
def start_benchmark(
    request: Request,
    background: BackgroundTasks,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    scope: Literal["smoke", "full"] = "smoke",
):
    expected = getenv("PERFORMANCE_RUN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(503, "Dashboard benchmark runs are disabled.")
    if not credentials or not compare_digest(credentials.credentials.encode(), expected.encode()):
        raise HTTPException(401, "Enter a valid performance run token.", headers={"WWW-Authenticate": "Bearer"})
    publication = getattr(request.app.state, "arize_publication", None)
    if publication and publication["status"] == "running":
        raise HTTPException(409, "Wait for startup publication to finish before starting a benchmark.")
    if reason := runner_unavailable():
        raise HTTPException(503, reason)
    with job_lock:
        if job["status"] == "running":
            raise HTTPException(409, "A dashboard benchmark is already running.")
        job.update(status="running", phase="Validating benchmark fixtures")
        current_job = dict(job)
    background.add_task(run_job, scope)
    return current_job
