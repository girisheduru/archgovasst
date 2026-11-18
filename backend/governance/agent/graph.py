"""Run an evidence review with two human checkpoints."""

from datetime import UTC, datetime

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..api.tracing import trace_node
from ..standards_store.catalog import load_rules
from .evidence import extract_evidence_with_llm
from .policy import assess_evidence_gaps
from .state import State


def retrieve_applicable_rules(state: State):
    return {"rules": load_rules(datetime.fromisoformat(state["as_of"]).date(), state["document_type"])}


def audit(state: State, checkpoint: str, decision: dict):
    return [
        *state.get("audit", []),
        {"checkpoint": checkpoint, **decision, "at": datetime.now(UTC).isoformat()},
    ]


def confirm_evidence(state: State):
    decision = interrupt({"checkpoint": "confirm_evidence"})
    return {
        "stage": "rejected" if decision["decision"] == "reject" else "confirmed",
        "audit": audit(state, "confirm_evidence", decision),
    }


def mark_report_ready(_state: State):
    return {"stage": "approve_report"}


def approve_report(state: State):
    decision = interrupt({"checkpoint": "approve_report"})
    return {
        "stage": "approved" if decision["decision"] == "approve" else "rejected",
        "audit": audit(state, "approve_report", decision),
    }


def after_confirmation(state: State):
    return "rejected" if state["stage"] == "rejected" else "confirmed"


def compile_workflow(checkpointer):
    graph = StateGraph(State)
    for node in (
        retrieve_applicable_rules,
        extract_evidence_with_llm,
        confirm_evidence,
        assess_evidence_gaps,
        mark_report_ready,
        approve_report,
    ):
        graph.add_node(node.__name__, trace_node(node))
    graph.add_edge(START, "retrieve_applicable_rules")
    graph.add_edge("retrieve_applicable_rules", "extract_evidence_with_llm")
    graph.add_edge("extract_evidence_with_llm", "confirm_evidence")
    graph.add_conditional_edges(
        "confirm_evidence",
        after_confirmation,
        {"confirmed": "assess_evidence_gaps", "rejected": END},
    )
    graph.add_edge("assess_evidence_gaps", "mark_report_ready")
    graph.add_edge("mark_report_ready", "approve_report")
    graph.add_edge("approve_report", END)
    return graph.compile(checkpointer=checkpointer)
