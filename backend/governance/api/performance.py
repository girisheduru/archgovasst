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
from ..evaluation.publish import arize_api_key, publish_bundled_assets
from ..performance import read_report, save_report
from ..run_application_tests import run_in_subprocess

router = APIRouter(prefix="/api/performance", tags=["Performance"])
bearer = HTTPBearer(auto_error=False)
logger = getLogger(__name__)
job_lock = Lock()
job = {"status": "idle"}
Action = Literal["benchmark", "publish", "tests", "fixtures"]
PHASES = {
    "benchmark": "Validating benchmark fixtures",
    "publish": "Publishing the dataset and Prompt Hub templates",
    "tests": "Running application tests",
    "fixtures": "Validating benchmark fixtures",
}
COMPLETION = {
    "benchmark": "Benchmark finished.",
    "publish": "Arize assets published.",
    "tests": "Application tests passed.",
    "fixtures": "Benchmark fixtures validated.",
}


def missing_dependency(*packages):
    try:
        for package in packages:
            version(package)
    except PackageNotFoundError as exc:
        return f"Install {exc.name} in the backend environment."
    return None


def controls_unavailable():
    if not getenv("PERFORMANCE_RUN_TOKEN", "").strip():
        return "Set PERFORMANCE_RUN_TOKEN on the backend to enable dashboard actions."
    return None


def action_availability():
    benchmark_settings = missing_benchmark_settings()
    benchmark_settings_error = (
        f"Configure {', '.join(benchmark_settings)} on the backend."
        if benchmark_settings else None
    )
    publish_settings_error = (
        None if getenv("ARIZE_SPACE_ID", "").strip() and arize_api_key()
        else "Configure ARIZE_SPACE_ID and an Arize key with publishing access."
    )
    arize_dependencies = missing_dependency("arize", "openpyxl")
    return {
        "benchmark": benchmark_settings_error or arize_dependencies,
        "publish": publish_settings_error or arize_dependencies,
        "tests": missing_dependency("httpx"),
        "fixtures": missing_dependency("openpyxl"),
    }


def update_job(status: str, phase: str, message: str | None = None):
    with job_lock:
        job.update(status=status, phase=phase, message=message)


def run_job(action: Action, scope: Literal["smoke", "full"]):
    try:
        if action == "publish":
            publish_bundled_assets(getenv("ARIZE_SPACE_ID", "").strip(), arize_api_key())
        elif action == "tests":
            if run_in_subprocess() != 0:
                update_job("failed", PHASES[action], "Application tests did not pass. Check the test results and backend logs.")
                return
        else:
            cases, rules = load_dataset()
            available_case_count = len(cases)
            save_report("fixtures", {**fixture_summary(cases, rules), "available_case_count": available_case_count})
            if action == "benchmark":
                if scope == "smoke":
                    case_id = min(cases)
                    cases = {case_id: cases[case_id]}
                run_benchmark(cases, rules, available_case_count, on_phase=lambda phase: update_job("running", phase))
    except Exception as exc:
        phase = job["phase"]
        status = getattr(exc, "status", getattr(exc, "status_code", None))
        logger.error("Performance action failed during %s (%s, status %s).", phase, type(exc).__name__, status)
        update_job("failed", phase, f"Failed while {phase.lower()}. Check the backend logs.")
    else:
        update_job("complete", PHASES[action], COMPLETION[action])


@router.get("")
def get_performance(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    with job_lock:
        current_job = dict(job)
    actions = action_availability()
    controls = controls_unavailable()
    return {
        "assets": read_report("assets"),
        "benchmark": read_report("benchmark"),
        "fixtures": read_report("fixtures"),
        "tests": read_report("tests"),
        "job": current_job,
        "arize_publication": getattr(request.app.state, "arize_publication", None),
        "actions": actions,
        "controls_unavailable": controls,
        "runner_unavailable": controls or actions["benchmark"],
    }


@router.post("/{action}", status_code=202)
def start_action(
    action: Action,
    request: Request,
    background: BackgroundTasks,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    scope: Literal["smoke", "full"] = "smoke",
):
    expected = getenv("PERFORMANCE_RUN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(503, "Dashboard actions are disabled.")
    if not credentials or not compare_digest(credentials.credentials.encode(), expected.encode()):
        raise HTTPException(401, "Enter a valid performance run token.", headers={"WWW-Authenticate": "Bearer"})
    publication = getattr(request.app.state, "arize_publication", None)
    if action in ("benchmark", "publish") and publication and publication["status"] == "running":
        raise HTTPException(409, "Wait for startup publication to finish before starting this action.")
    if reason := action_availability()[action]:
        raise HTTPException(503, reason)
    with job_lock:
        if job["status"] == "running":
            raise HTTPException(409, "A dashboard action is already running.")
        job.update(action=action, status="running", phase=PHASES[action], message=None)
        current_job = dict(job)
    background.add_task(run_job, action, scope)
    return current_job
