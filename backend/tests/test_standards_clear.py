import unittest
from unittest.mock import patch

from chromadb.errors import NotFoundError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.governance.api.standards_import import router


class ClearStandardsTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = self.enterContext(TestClient(app))
        self.connect = self.enterContext(patch("backend.governance.api.standards_import.standards_client"))
        self.delete_collection = self.connect.return_value.delete_collection
        self.env = self.enterContext(patch.dict("os.environ", {
            "STANDARDS_IMPORT_TOKEN": "test-token",
            "CHROMA_STANDARDS_COLLECTION": "test-governance-standards",
        }))

    def clear(self, token="test-token"):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.post("/api/standards/clear", headers=headers)

    def test_missing_or_invalid_token_cannot_delete(self):
        for token in ("", "invalid"):
            with self.subTest(token=token):
                self.assertEqual(self.clear(token).status_code, 401)
        self.connect.assert_not_called()

    def test_unconfigured_token_disables_reset(self):
        self.env["STANDARDS_IMPORT_TOKEN"] = ""
        self.assertEqual(self.clear().status_code, 503)
        self.connect.assert_not_called()

    def test_deletes_configured_collection(self):
        self.assertEqual(self.clear().json(), {"cleared": True})
        self.delete_collection.assert_called_once_with("test-governance-standards")

    def test_absent_collection_reports_already_empty(self):
        self.delete_collection.side_effect = NotFoundError("Missing collection")
        self.assertEqual(self.clear().json(), {"cleared": False})

    def test_chroma_failure_returns_error(self):
        self.delete_collection.side_effect = RuntimeError("Chroma unavailable")
        with self.assertLogs("backend.governance.api.standards_import", level="ERROR"):
            response = self.clear()
        self.assertEqual(response.status_code, 503)
        self.assertIn("Could not clear", response.json()["detail"])
