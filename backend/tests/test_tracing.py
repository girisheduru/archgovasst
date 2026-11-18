"""Verify trace hierarchy through the API and the real interrupted LangGraph."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from backend.governance.application import app
from backend.governance.agent.evidence import Extraction
from backend.governance.api.tracing import trace_operation


class ReviewTracingTests(unittest.TestCase):
    def setUp(self):
        self.provider = TracerProvider()
        self.exporter = InMemorySpanExporter()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.addCleanup(self.provider.shutdown)
        self.rule = {
            "id": "rule-1", "standard": "Test standard", "effective_date": "2026-01-01",
            "quote": "Private rule text", "evidence_required": "Private guidance",
            "gap_risk": "medium", "document_types": ["solution_design"],
        }
        self.collection = Mock()
        self.collection.get.return_value = {"documents": [json.dumps(self.rule)]}
        self.chroma = self.enterContext(patch(
            "backend.governance.standards_store.catalog.standards_client"
        ))
        self.chroma.return_value.get_collection.return_value = self.collection
        self.openai = self.enterContext(patch("backend.governance.providers.openai.OpenAI"))
        self.openai.return_value.__enter__.return_value.responses.parse.return_value = SimpleNamespace(
            model="test-model", output_parsed=Extraction(evidence=[]),
            usage=SimpleNamespace(input_tokens=20, output_tokens=5, total_tokens=25),
        )
        self.enterContext(patch.dict("os.environ", {"OPENAI_API_KEY": "test", "EVIDENCE_RETRIEVAL_MODE": "hybrid"}))
        self.enterContext(patch("backend.governance.application.configure_arize", return_value=self.provider))
        self.parse_document = self.enterContext(patch(
            "backend.governance.api.document_reviews.parse_document",
            return_value={"section": "Private design text"},
        ))
        self.client = self.enterContext(TestClient(app))

    def upload(self):
        return self.client.post(
            "/api/reviews", files={"document": ("private.pdf", b"Private document")},
            data={"document_type": "solution_design", "declared_tier": "low"},
        )

    def test_nodes_retrieval_and_llm_are_children_across_checkpoint_requests(self):
        self.parse_document.return_value = {f"Page {i}": "Private design text " * 90 for i in range(4)}
        embeddings = self.openai.return_value.__enter__.return_value.embeddings
        embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(index=i, embedding=[1.0, 0.0]) for i in range(5)],
            usage=SimpleNamespace(total_tokens=50),
        )
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        review_id = response.json()["review_id"]
        for checkpoint in ("confirm_evidence", "approve_report"):
            response = self.client.post(f"/api/reviews/{review_id}/decision", json={
                "checkpoint": checkpoint, "decision": "approve", "reviewer": "Private reviewer",
            })
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["stage"], "approved")
        spans = self.exporter.get_finished_spans()
        roots = [span for span in spans if span.parent is None]
        self.assertEqual([span.name for span in roots], [
            "start_document_review", "confirm_evidence", "approve_report",
        ])
        by_id = {span.context.span_id: span for span in spans}
        expected_parents = {
            "parse_document": "start_document_review",
            "retrieve_applicable_rules": "start_document_review",
            "extract_evidence_with_llm": "start_document_review",
            "chroma.load_rules": "retrieve_applicable_rules",
            "design.rank_passages": "extract_evidence_with_llm",
            "openai.embeddings.create": "design.rank_passages",
            "design.search_full_document": "extract_evidence_with_llm",
            "assess_evidence_gaps": "confirm_evidence", "mark_report_ready": "confirm_evidence",
        }
        for name, parent in expected_parents.items():
            span = next(span for span in spans if span.name == name)
            self.assertEqual(by_id[span.parent.span_id].name, parent)
            self.assertEqual(span.context.trace_id, by_id[span.parent.span_id].context.trace_id)
        waits = [span for span in spans if span.attributes.get("review.waiting_for_decision")]
        self.assertEqual([span.name for span in waits], ["confirm_evidence", "approve_report"])
        for request_span in roots[1:]:
            self.assertTrue(any(
                span.name == request_span.name and span.parent == request_span.context
                for span in spans
            ))
        llm_calls = [span for span in spans if span.name == "openai.responses.parse"]
        self.assertEqual([by_id[span.parent.span_id].name for span in llm_calls], [
            "extract_evidence_with_llm", "design.search_full_document",
        ])
        for llm in llm_calls:
            self.assertEqual(llm.attributes["openinference.span.kind"], "LLM")
            self.assertEqual(llm.attributes["llm.token_count.total"], 25)
        embed = next(span for span in spans if span.name == "openai.embeddings.create")
        self.assertEqual(embed.attributes["embedding.token_count"], 50)
        for span in spans:
            self.assertEqual(span.attributes["session.id"], review_id)
            self.assertEqual(span.status.status_code, StatusCode.OK)
            self.assertFalse(span.events)
            self.assertNotIn("Private", str(dict(span.attributes)))
        with trace_operation("outside_review"):
            pass
        self.assertEqual(len(self.exporter.get_finished_spans()), len(spans))

    def test_retrieval_failure_marks_child_and_root_as_errors(self):
        self.collection.get.side_effect = RuntimeError("Private database details")
        response = self.upload()
        self.assertEqual(response.status_code, 503)
        spans = self.exporter.get_finished_spans()
        for name in ("chroma.load_rules", "retrieve_applicable_rules", "start_document_review"):
            span = next(span for span in spans if span.name == name)
            self.assertEqual(span.status.status_code, StatusCode.ERROR)
            self.assertIsNone(span.status.description)
            self.assertFalse(span.events)

    def test_tracing_disabled_preserves_review(self):
        app.state.tracer = None
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertFalse(self.exporter.get_finished_spans())


if __name__ == "__main__":
    unittest.main()
