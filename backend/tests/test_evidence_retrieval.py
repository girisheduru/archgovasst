"""Check retrieval scope, citation validation, and the full-document baseline."""

import json
import unittest
from unittest.mock import patch

from backend.governance.agent.evidence import Evidence, Extraction, extract
from backend.governance.agent.retrieval import build_passages, rank_passages


class EvidenceRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.sections = {f"Page {i}": f"Section {i} " + "unrelated text " * 140 for i in range(1, 6)}
        self.sections["Page 1"] += "All volumes are encrypted."
        self.sections["Page 5"] += "The system ships audit logs to the security team."
        self.rules = [
            {"id": "encryption", "quote": "Encrypt stored data", "evidence_required": "Encrypted volumes"},
            {"id": "audit", "quote": "Send audit logs", "evidence_required": "Audit log destination"},
            {"id": "backup", "quote": "Back up databases", "evidence_required": "Backup schedule"},
        ]
        self.state = {"sections": self.sections, "rules": self.rules}

    def test_rank_uses_both_keyword_and_semantic_signals(self):
        passages = [{"P1": "audit logs"}, {"P2": "records events"}, {"P3": "unrelated"}, {"P4": "misc"}]
        with patch("backend.governance.agent.retrieval.embed_texts", return_value=[
            [0, 1], [1, 0], [0, -1], [-1, 0], [1, 0],
        ]):
            ranked = rank_passages([self.rules[1]], passages)
        self.assertEqual(set(ranked["audit"]), {0, 1})

    def test_ranked_quotes_must_belong_to_rule_and_unresolved_rules_get_full_document(self):
        passages = build_passages(self.sections)
        chosen = next(i for i, passage in enumerate(passages) if "All volumes are encrypted." in passage.get("Page 1", ""))
        rankings = {rule["id"]: [chosen] for rule in self.rules}
        encryption = Evidence(rule_id="encryption", source="Page 1", quote="All volumes are encrypted.")
        audit = Evidence(rule_id="audit", source="Page 5", quote="The system ships audit logs to the security team.")
        invented = Evidence(rule_id="backup", source="Page 5", quote="Backups run hourly.")
        baseline_response = Extraction(evidence=[encryption, audit, invented])
        responses = [Extraction(evidence=[encryption, audit]), Extraction(evidence=[audit, invented]), baseline_response]
        with (
            patch.dict("os.environ", {"EVIDENCE_RETRIEVAL_MODE": "hybrid"}),
            patch("backend.governance.agent.evidence.rank_passages", return_value=rankings),
            patch("backend.governance.agent.evidence.parse_response", side_effect=responses) as parse,
        ):
            result = extract(self.state)
            with patch.dict("os.environ", {"EVIDENCE_RETRIEVAL_MODE": "full_document"}):
                baseline = extract(self.state)
        ranked, fallback, original = [json.loads(call.args[2]) for call in parse.call_args_list]
        self.assertEqual(list(ranked["passages"]), [str(chosen)])
        self.assertLess(len(json.dumps(ranked)), len(json.dumps(original)))
        self.assertEqual([rule["id"] for rule in fallback["rules"]], ["audit", "backup"])
        self.assertEqual(fallback["document"], self.sections)
        self.assertEqual(set(result["evidence"]), {"encryption", "audit"})
        self.assertEqual(result, baseline)

    def test_baseline_and_failed_ranking_search_all_applicable_rules(self):
        for mode in ("full_document", "hybrid"):
            with (
                self.subTest(mode=mode),
                patch.dict("os.environ", {"EVIDENCE_RETRIEVAL_MODE": mode}),
                patch("backend.governance.agent.evidence.rank_passages", side_effect=ValueError) as rank,
                patch("backend.governance.agent.evidence.parse_response", return_value=Extraction(evidence=[])) as parse,
            ):
                self.assertEqual(extract(self.state)["evidence"], {})
                self.assertEqual(rank.call_count, int(mode == "hybrid"))
                self.assertEqual(parse.call_count, 1)
                payload = json.loads(parse.call_args.args[2])
                self.assertEqual(payload["document"], self.sections)
                self.assertEqual([rule["id"] for rule in payload["rules"]], [rule["id"] for rule in self.rules])
