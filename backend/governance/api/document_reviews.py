from datetime import date
from hashlib import sha256
from os import getenv
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from langgraph.types import Command
from pydantic import BaseModel, Field, StringConstraints

from ..agent.documents import MAX_UPLOAD_BYTES, parse_document
from ..agent.evidence import ModelUnavailable, extract_supporting_evidence, suggest_gap_action
from ..review_report import render_review_report
from ..standards_store.catalog import StandardsUnavailable
from ..standards_store.models import DocumentType, RiskTier
from .tracing import trace_operation, trace_review

router = APIRouter(prefix="/api/reviews", tags=["Document reviews"])
FindingComment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class Decision(BaseModel):
    checkpoint: Literal["confirm_evidence", "approve_report"]
    decision: Literal["approve", "reject"]
    reviewer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    comments: dict[str, FindingComment] = Field(default_factory=dict)
    supporting_evidence: dict[str, str] = Field(default_factory=dict)


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
                "supporting_candidate": state.get("supporting_candidates", {}).get(rule["id"]),
            }
            for rule in state["rules"]
        ],
        "findings": state.get("findings", []),
        "risk_tier": state.get("risk_tier"),
    }


def _read_document(document: UploadFile):
    filename = Path(document.filename or "").name
    payload = document.file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Upload a document of at most 10 MB.")
    try:
        with trace_operation("parse_document", "TOOL") as span:
            sections = parse_document(filename, payload)
            span.set_attribute("document.section_count", len(sections))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, "Could not extract text from the document.") from exc
    return filename, payload, sections


def _gap_rule(state: dict, rule_id: str):
    if "stage" not in state:
        raise HTTPException(404, "Review not found.")
    for rule in state["rules"]:
        if rule["id"] == rule_id:
            if rule_id in state["evidence"]:
                raise HTTPException(409, "This rule already has evidence.")
            return rule
    raise HTTPException(404, "Rule not found in this review.")


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
        filename, _, sections = _read_document(document)

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


@router.post("/{review_id}/gap-guidance")
def gap_guidance(review_id: UUID, rule_id: Annotated[str, Form()], request: Request):
    state = request.app.state.workflow.get_state(_config(review_id)).values
    rule = _gap_rule(state, rule_id)
    with trace_review(request.app.state.tracer, "suggest_gap_action", review_id):
        try:
            return suggest_gap_action(state["extraction_model"], rule, state["sections"])
        except ModelUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc


@router.post("/{review_id}/supporting-evidence")
def recheck_supporting_evidence(
    review_id: UUID,
    request: Request,
    rule_id: Annotated[str, Form()],
    document: Annotated[UploadFile, File()],
):
    config = _config(review_id)
    workflow = request.app.state.workflow
    state = workflow.get_state(config).values
    rule = _gap_rule(state, rule_id)
    if state["stage"] != "confirm_evidence":
        raise HTTPException(409, "Supporting documents can only be checked before evidence confirmation.")
    previous = state.get("supporting_candidates", {}).get(rule_id)

    with trace_review(request.app.state.tracer, "recheck_supporting_evidence", review_id):
        filename, payload, sections = _read_document(document)
        try:
            evidence = extract_supporting_evidence(state["extraction_model"], rule, sections)
        except ModelUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

        with request.app.state.decision_lock:
            current = workflow.get_state(config).values
            if current["stage"] != "confirm_evidence":
                raise HTTPException(409, "The evidence checkpoint is no longer pending. Refresh the review.")
            candidates = current.get("supporting_candidates", {})
            if candidates.get(rule_id) != previous:
                raise HTTPException(409, "This rule has a newer recheck. Refresh the review.")
            if evidence:
                candidate = {
                    "id": str(uuid4()),
                    "evidence": {**evidence, "document": filename, "document_sha256": sha256(payload).hexdigest()},
                }
                updated = workflow.update_state(
                    config, {"supporting_candidates": {**candidates, rule_id: candidate}},
                    as_node="extract_evidence_with_llm",
                )
                current = workflow.get_state(updated).values
        return _view(review_id, current)


@router.get("/{review_id}/report.pdf", response_class=Response, responses={
    200: {"content": {"application/pdf": {}}},
})
def download_report(review_id: UUID, request: Request):
    review = get_review(review_id, request)
    if review["stage"] not in ("approved", "rejected") or not review["risk_tier"]:
        raise HTTPException(409, "A final review report is not available.")

    return Response(
        render_review_report(review),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="review-{review_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/{review_id}/decision")
def decide(review_id: UUID, decision: Decision, request: Request):
    with trace_review(request.app.state.tracer, decision.checkpoint, review_id):
        config = _config(review_id)
        workflow = request.app.state.workflow
        with request.app.state.decision_lock:
            current = _view(review_id, workflow.get_state(config).values)
            if current["stage"] != decision.checkpoint:
                raise HTTPException(409, "This checkpoint is no longer pending. Refresh the review.")
            rows = current["extraction"] if decision.checkpoint == "confirm_evidence" else current["findings"]
            if decision.comments.keys() - {row["rule_id"] for row in rows}:
                raise HTTPException(422, "Finding comments must refer to rules in this checkpoint.")
            if decision.supporting_evidence:
                if decision.checkpoint != "confirm_evidence" or decision.decision != "approve":
                    raise HTTPException(422, "Supporting evidence can only be included when confirming evidence.")
                candidates = {
                    row["rule_id"]: row["supporting_candidate"]["id"]
                    for row in rows if row["supporting_candidate"]
                }
                if any(candidates.get(rule_id) != candidate_id
                       for rule_id, candidate_id in decision.supporting_evidence.items()):
                    raise HTTPException(409, "A selected supporting quote has changed. Refresh the review.")
            record = decision.model_dump()
            if not decision.supporting_evidence:
                record.pop("supporting_evidence")
            state = workflow.invoke(Command(resume=record), config)
        return _view(review_id, state)
