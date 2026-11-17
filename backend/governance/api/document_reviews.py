from datetime import date
from os import getenv
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from langgraph.types import Command
from pydantic import BaseModel, StringConstraints

from ..agent.documents import MAX_UPLOAD_BYTES, parse_document
from ..agent.evidence import ModelUnavailable
from ..standards_store.catalog import StandardsUnavailable
from ..standards_store.models import DocumentType, RiskTier
from .tracing import trace_review

router = APIRouter(prefix="/api/reviews", tags=["Document reviews"])


class Decision(BaseModel):
    checkpoint: Literal["confirm_evidence", "approve_report"]
    decision: Literal["approve", "reject"]
    reviewer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


def _config(review_id: UUID):
    return {"configurable": {"thread_id": str(review_id)}}


def _view(review_id: UUID, state: dict):
    if "stage" not in state:
        raise HTTPException(404, "Review not found.")
    return {
        "review_id": str(review_id),
        "filename": state["filename"],
        "document_type": state["document_type"],
        "declared_tier": state["declared_tier"],
        "as_of": state["as_of"],
        "stage": state["stage"],
        "extraction_model": state["extraction_model"],
        "audit": state.get("audit", []),
        "extraction": [
            {
                "rule_id": rule["id"],
                "standard": rule["standard"],
                "effective_date": rule["effective_date"],
                "rule_quote": rule["quote"],
                "evidence_required": rule["evidence_required"],
                "evidence": state["evidence"].get(rule["id"]),
            }
            for rule in state["rules"]
        ],
        "findings": state.get("findings", []),
        "risk_tier": state.get("risk_tier"),
    }


@router.post("", status_code=201)
def start_review(
    request: Request,
    document: Annotated[UploadFile, File()],
    document_type: Annotated[DocumentType, Form()],
    declared_tier: Annotated[RiskTier, Form()],
    as_of: Annotated[date | None, Form()] = None,
):
    review_id = uuid4()
    with trace_review(request.app.state.tracer, "start_document_review", review_id):
        if not getenv("OPENAI_API_KEY", "").strip():
            raise HTTPException(503, "Configure OPENAI_API_KEY on the backend before starting a review.")
        filename = Path(document.filename or "").name
        payload = document.file.read(MAX_UPLOAD_BYTES + 1)
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Upload a document of at most 10 MB.")
        try:
            sections = parse_document(filename, payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(422, "Could not extract text from the document.") from exc

        try:
            state = request.app.state.workflow.invoke(
                {
                    "filename": filename,
                    "document_type": document_type,
                    "declared_tier": declared_tier,
                    "as_of": (as_of or date.today()).isoformat(),
                    "sections": sections,
                },
                _config(review_id),
            )
        except (StandardsUnavailable, ModelUnavailable) as exc:
            request.app.state.checkpointer.delete_thread(str(review_id))
            raise HTTPException(503, str(exc)) from exc

        return _view(review_id, state)


@router.get("/{review_id}")
def get_review(review_id: UUID, request: Request):
    snapshot = request.app.state.workflow.get_state(_config(review_id))
    return _view(review_id, snapshot.values)


@router.post("/{review_id}/decision")
def decide(review_id: UUID, decision: Decision, request: Request):
    with trace_review(request.app.state.tracer, decision.checkpoint, review_id):
        config = _config(review_id)
        workflow = request.app.state.workflow
        with request.app.state.decision_lock:
            current = _view(review_id, workflow.get_state(config).values)
            if current["stage"] != decision.checkpoint:
                raise HTTPException(409, "This checkpoint is no longer pending. Refresh the review.")
            state = workflow.invoke(Command(resume=decision.model_dump()), config)
        return _view(review_id, state)
