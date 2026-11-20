"""Persist the latest performance reports for the dashboard."""

import json
from datetime import UTC, datetime
from os import getenv
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

ReportKind = Literal["assets", "benchmark", "fixtures", "tests"]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def report_path(kind: ReportKind) -> Path:
    directory = PROJECT_ROOT / getenv("PERFORMANCE_REPORT_DIR", ".performance")
    return directory / f"{kind}.json"


def save_report(kind: ReportKind, summary: dict) -> None:
    path = report_path(kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {**summary, "completed_at": datetime.now(UTC).isoformat()}
    # Write beside the destination so an HTTP request can only see a complete report.
    file = NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False)
    temporary = Path(file.name)
    try:
        with file:
            json.dump(report, file, allow_nan=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_report(kind: ReportKind) -> dict:
    try:
        report = json.loads(report_path(kind).read_text(encoding="utf-8"))
        if not isinstance(report, dict) or not isinstance(report.get("completed_at"), str):
            return {"status": "unavailable"}
        return {"status": "available", "report": report}
    except FileNotFoundError:
        return {"status": "pending"}
    except (OSError, ValueError):
        return {"status": "unavailable"}
