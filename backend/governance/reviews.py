from contextlib import nullcontext
from random import choice
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel


router = APIRouter()


class ReviewArea(BaseModel):
    title: str
    finding: str
    next_step: str


class SampleReview(BaseModel):
    sample: Literal[True] = True
    system_name: str
    review_areas: list[ReviewArea]


SYSTEM_NAMES = ("Policy Search Assistant", "Case Summary Assistant", "Service Desk Assistant")

REVIEW_FINDINGS = {
    "Security & privacy": (
        ("Access to source records is role-based.", "Confirm access is revoked when staff change roles."),
        ("The proposal leaves prompt retention open.", "Agree on a retention period with the data owner."),
    ),
    "Architecture fit": (
        ("The proposed service uses a shared model gateway.", "Record the gateway dependency in the architecture diagram."),
        ("The proposal adds a new document indexing service.", "Compare the proposal with the shared indexing service."),
    ),
    "Operational readiness": (
        ("The proposal identifies a service owner.", "Confirm the escalation path for out-of-hours incidents."),
        ("The proposal includes monitoring for request failures.", "Assign an owner for alert triage and test the alert."),
    ),
}


@router.get("/api/reviews/sample", response_model=SampleReview)
def get_sample_review(request: Request, response: Response) -> SampleReview:
    """Return fictional review details for the landing page's three review areas."""
    response.headers["Cache-Control"] = "no-store"
    tracer = request.app.state.tracer
    span = (
        tracer.start_as_current_span(
            "generate_sample_review", attributes={"openinference.span.kind": "CHAIN"}
        )
        if tracer
        else nullcontext()
    )
    with span:
        review_areas = []
        for title, findings in REVIEW_FINDINGS.items():
            finding, next_step = choice(findings)
            review_areas.append(ReviewArea(title=title, finding=finding, next_step=next_step))

        return SampleReview(system_name=choice(SYSTEM_NAMES), review_areas=review_areas)
