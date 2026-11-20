from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from os import getenv

from langgraph.errors import GraphInterrupt
from opentelemetry.trace import INVALID_SPAN_CONTEXT, NonRecordingSpan, StatusCode

_review_trace = ContextVar("review_trace", default=None)


@contextmanager
def trace_operation(name, kind="CHAIN", attributes=None):
    context = _review_trace.get()
    if context is None:
        yield NonRecordingSpan(INVALID_SPAN_CONTEXT)
        return

    tracer, review_id = context
    with tracer.start_as_current_span(
        name,
        attributes={
            **(attributes or {}),
            "openinference.span.kind": kind,
            "session.id": str(review_id),
        },
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except GraphInterrupt:
            span.set_attribute("review.waiting_for_decision", True)
            span.set_status(StatusCode.OK)
            raise
        except Exception:
            span.set_status(StatusCode.ERROR)
            raise
        else:
            span.set_status(StatusCode.OK)


def trace_node(node):
    @wraps(node)
    def traced(state):
        with trace_operation(node.__name__) as span:
            result = node(state)
            if "stage" in result:
                span.set_attribute("review.stage", result["stage"])
            return result

    return traced


@contextmanager
def trace_review(tracer, name, review_id):
    if tracer is None:
        yield
        return

    token = _review_trace.set((tracer, review_id))
    try:
        with trace_operation(name):
            yield
    finally:
        _review_trace.reset(token)


def configure_arize():
    space_id = getenv("ARIZE_SPACE_ID", "").strip()
    api_key = getenv("ARIZE_API_KEY", "").strip()
    if not api_key and (not space_id or getenv("ARIZE_EVAL_API_KEY", "").strip()):
        return None
    if not space_id or not api_key:
        raise RuntimeError("Arize AX requires both ARIZE_SPACE_ID and ARIZE_API_KEY.")

    from arize.otel import register

    return register(
        space_id=space_id,
        api_key=api_key,
        project_name=getenv("ARIZE_PROJECT_NAME", "").strip() or "archgovasst",
        set_global_tracer_provider=False,
        verbose=False,
    )
