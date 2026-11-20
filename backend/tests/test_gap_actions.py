"""Check gap guidance and supporting evidence through the live review workflow."""

import json
import unittest
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.governance.agent.evidence import Evidence, Extraction, GapGuidance
from backend.governance.application import app
from backend.governance.evaluation.metrics import AnswerKey, evaluate


def word_document(text):
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class GapActionsTests(unittest.TestCase):
    def setUp(self):
        self.rule = {
            "id": "restore", "standard": "Continuity", "effective_date": "2026-01-01",
            "quote": "Test backup restores.", "evidence_required": "Restore test date and outcome.",
            "gap_risk": "high", "document_types": ["solution_design"],
        }
        self.enterContext(patch("backend.governance.agent.graph.load_rules", return_value=[self.rule]))
        self.enterContext(patch("backend.governance.application.configure_arize", return_value=None))
        self.enterContext(patch.dict("os.environ", {"OPENAI_API_KEY": "test"}))
        self.model = self.enterContext(patch("backend.governance.agent.evidence.parse_response"))
        self.model.return_value = Extraction(evidence=[])
        self.client = self.enterContext(TestClient(app))
        response = self.client.post(
            "/api/reviews", files={"document": ("design.docx", word_document("Backups are enabled."))},
            data={"document_type": "solution_design", "declared_tier": "low", "as_of": "2026-02-01"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.url = f'/api/reviews/{response.json()["review_id"]}'
        self.quote = "A backup restore succeeded during the test on 2026-01-15."
        self.supporting_file = word_document(self.quote)

    def recheck(self, quote):
        self.model.return_value = Extraction(evidence=[
            Evidence(rule_id="restore", source="Paragraph 1", quote=quote),
        ])
        return self.client.post(
            f"{self.url}/supporting-evidence", data={"rule_id": "restore"},
            files={"document": ("test-record.docx", self.supporting_file)},
        )

    def confirm(self, selection=None):
        return self.client.post(f"{self.url}/decision", json={
            "checkpoint": "confirm_evidence", "decision": "approve", "reviewer": "Reviewer",
            "supporting_evidence": selection or {},
        })

    def test_guidance_uses_the_rule_and_leaves_extraction_unchanged(self):
        before = self.client.get(self.url).json()
        self.model.return_value = GapGuidance(
            missing_evidence="Restore date and outcome", next_step="Provide the latest test record.",
        )
        response = self.client.post(f"{self.url}/gap-guidance", data={"rule_id": "restore"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["next_step"], "Provide the latest test record.")
        inputs = json.loads(self.model.call_args.args[2])
        self.assertEqual(inputs["rule"]["id"], "restore")
        self.assertEqual(inputs["design_passages"], [{"Paragraph 1": "Backups are enabled."}])
        self.assertEqual(before, self.client.get(self.url).json())

    def test_verified_quote_requires_current_reviewer_selection_and_exports_its_source(self):
        response = self.recheck(self.quote)
        self.assertEqual(response.status_code, 200, response.text)
        review = response.json()
        row = review["extraction"][0]
        candidate = row["supporting_candidate"]
        self.assertEqual(review["stage"], "confirm_evidence")
        self.assertIsNone(row["evidence"])
        self.assertEqual(self.client.get(self.url).json(), review)
        inputs = json.loads(self.model.call_args.args[2])
        self.assertEqual([rule["id"] for rule in inputs["rules"]], ["restore"])
        self.assertEqual(inputs["document"], {"Paragraph 1": self.quote})

        replacement = self.recheck(self.quote).json()["extraction"][0]["supporting_candidate"]
        self.assertEqual(self.confirm({"restore": candidate["id"]}).status_code, 409)
        response = self.confirm({"restore": replacement["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        review = response.json()
        self.assertEqual(review["stage"], "approve_report")
        self.assertEqual(review["risk_tier"], "low")
        self.assertEqual(review["findings"][0]["evidence"], replacement["evidence"])
        self.assertEqual(self.recheck(self.quote).status_code, 409)
        self.assertEqual(
            self.client.post(f"{self.url}/gap-guidance", data={"rule_id": "restore"}).status_code, 409,
        )
        self.client.post(f"{self.url}/decision", json={
            "checkpoint": "approve_report", "decision": "approve", "reviewer": "Reviewer",
        }).raise_for_status()
        report = self.client.get(f"{self.url}/report.pdf")
        report.raise_for_status()
        reader = PdfReader(BytesIO(report.content))
        self.assertIn("test-record.docx", "\n".join(page.extract_text() for page in reader.pages))

        key = AnswerKey(not_evidenced_rule_ids=set(), risk_tier="low")
        design = {"Paragraph 1": "Backups are enabled."}
        self.assertEqual(evaluate(review, key, design, [self.rule])["source_citation_validity"], 0)
        supporting = {sha256(self.supporting_file).hexdigest(): {"Paragraph 1": self.quote}}
        self.assertEqual(
            evaluate(review, key, design, [self.rule], supporting)["source_citation_validity"], 1,
        )

    def test_unverified_or_unselected_quote_leaves_a_gap(self):
        self.assertIsNone(self.recheck("An invented quote.").json()["extraction"][0]["supporting_candidate"])
        self.assertIsNotNone(self.recheck(self.quote).json()["extraction"][0]["supporting_candidate"])
        response = self.confirm()
        self.assertEqual(response.status_code, 200, response.text)
        review = response.json()
        self.assertEqual(review["findings"][0]["status"], "not_evidenced")
        self.assertEqual(review["risk_tier"], "high")
        self.assertIsNone(review["extraction"][0]["supporting_candidate"])
        self.assertEqual(self.recheck(self.quote).status_code, 409)
