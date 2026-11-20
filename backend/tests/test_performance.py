import unittest
from asyncio import sleep, timeout
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.governance import application, evaluate
from backend.governance.api import performance
from backend.governance.application import app
from backend.governance.evaluation import publish
from backend.governance.evaluation.dataset import DesignCase
from backend.governance.evaluation.metrics import AnswerKey
from backend.governance.performance import save_report


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.dict("os.environ", {
            "PERFORMANCE_REPORT_DIR": directory,
            "PERFORMANCE_RUN_TOKEN": "run-token",
            "ARIZE_SPACE_ID": "test-space",
            "ARIZE_API_KEY": "tracing-key",
            "ARIZE_EVAL_API_KEY": "evaluation-key",
            "OPENAI_API_KEY": "openai-key",
        }))
        self.enterContext(patch("backend.governance.application.configure_arize", return_value=None))
        self.enterContext(patch.object(performance, "version", return_value="installed"))
        self.enterContext(patch.object(performance, "job", {"status": "idle"}))
        self.cases = {
            case_id: DesignCase(case_id, {}, case_id, "low", "review", AnswerKey(
                not_evidenced_rule_ids=set(), risk_tier="low",
            ))
            for case_id in ("SD-01", "SD-02")
        }
        self.enterContext(patch.object(performance, "load_dataset", return_value=(self.cases, [])))
        self.enterContext(patch.object(publish, "load_dataset", return_value=(self.cases, [])))
        self.sdk = Mock()
        self.enterContext(patch.dict("sys.modules", {
            "arize": SimpleNamespace(ArizeClient=self.sdk),
        }))
        self.dataset = self.enterContext(patch.object(
            publish, "publish_dataset", return_value=SimpleNamespace(id="dataset-id"),
        ))
        self.prompt = self.enterContext(patch.object(
            publish, "publish_prompt",
            side_effect=lambda client, space, template: {"name": template["name"], "prompt_id": template["name"]},
        ))
        self.experiment = self.enterContext(patch.object(
            evaluate, "run", return_value={"experiment_id": "experiment-id", "case_count": 1},
        ))
        with patch.object(application, "arize_api_key", return_value=""):
            self.client = self.enterContext(TestClient(app))
        self.headers = {"Authorization": "Bearer run-token"}

    def test_benchmark_publishes_assets_and_saves_dashboard_results(self):
        response = self.client.post("/api/performance/benchmark", headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "running")
        self.sdk.assert_called_once_with(api_key="evaluation-key")
        self.assertEqual(len(self.dataset.call_args.args[2]["examples"]), 1)
        self.assertEqual(self.prompt.call_count, 4)
        self.assertEqual(list(self.experiment.call_args.args[2]), ["SD-01"])
        result = self.client.get("/api/performance").json()
        self.assertEqual(result["job"]["status"], "complete")
        self.assertEqual(len(result["assets"]["report"]["prompts"]), 4)
        self.assertEqual(result["fixtures"]["report"]["case_count"], 2)
        self.assertEqual(result["benchmark"]["report"]["experiment_id"], "experiment-id")
        self.assertEqual(result["benchmark"]["report"]["available_case_count"], 2)

    def test_failed_experiment_keeps_published_assets_visible(self):
        self.experiment.side_effect = RuntimeError("private provider details")
        with self.assertLogs(performance.__name__, level="ERROR") as logs:
            self.assertEqual(self.client.post(
                "/api/performance/benchmark?scope=full", headers=self.headers,
            ).status_code, 202)
        self.assertEqual(len(self.dataset.call_args.args[2]["examples"]), 2)
        report = self.client.get("/api/performance")
        self.assertEqual(report.json()["job"]["status"], "failed")
        self.assertEqual(report.json()["assets"]["status"], "available")
        self.assertEqual(report.json()["benchmark"]["status"], "pending")
        self.assertNotIn("private provider details", report.text + str(logs.output))

    def test_start_requires_token_and_rejects_an_overlapping_run(self):
        url = "/api/performance/benchmark"
        self.assertEqual(self.client.post(url).status_code, 401)
        performance.update_job("running", "Testing concurrent request")
        self.assertEqual(self.client.post(url, headers=self.headers).status_code, 409)
        self.sdk.assert_not_called()

    def test_publish_action_uses_the_full_dataset_without_running_a_benchmark(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            response = self.client.post("/api/performance/publish", headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["action"], "publish")
        self.assertEqual(len(self.dataset.call_args.args[2]["examples"]), 2)
        self.assertEqual(self.prompt.call_count, 4)
        result = self.client.get("/api/performance").json()
        self.assertEqual(result["job"]["status"], "complete")
        self.assertEqual(result["assets"]["report"]["dataset_id"], "dataset-id")
        self.experiment.assert_not_called()

    def test_fixture_and_application_checks_work_without_service_credentials(self):
        def failing_tests():
            save_report("tests", {"passed": False, "tests_run": 1, "failures": 1})
            return 1

        with (
            patch.dict("os.environ", {
                "ARIZE_SPACE_ID": "", "ARIZE_EVAL_API_KEY": "", "ARIZE_API_KEY": "", "OPENAI_API_KEY": "",
            }),
            patch.object(performance, "run_in_subprocess", side_effect=failing_tests) as tests,
        ):
            self.assertEqual(self.client.post("/api/performance/fixtures", headers=self.headers).status_code, 202)
            result = self.client.get("/api/performance").json()
            self.assertEqual(result["job"]["action"], "fixtures")
            self.assertEqual(result["job"]["status"], "complete")
            self.assertEqual(result["fixtures"]["report"]["case_count"], 2)
            self.assertEqual(self.client.post("/api/performance/tests").status_code, 401)
            self.assertEqual(self.client.post("/api/performance/tests", headers=self.headers).status_code, 202)
            result = self.client.get("/api/performance").json()

        tests.assert_called_once_with()
        self.assertEqual(result["job"]["action"], "tests")
        self.assertEqual(result["job"]["status"], "failed")
        self.assertFalse(result["tests"]["report"]["passed"])
        self.sdk.assert_not_called()

    async def wait_for_startup_publication(self):
        async with timeout(3):
            while app.state.arize_publication["status"] == "running":
                await sleep(0.01)

    def test_startup_publishes_full_dataset_and_templates_in_background(self):
        release = Event()

        def publish_dataset(*args):
            if not release.wait(timeout=5):
                raise TimeoutError("Test did not release publishing.")
            return SimpleNamespace(id="startup-dataset")

        self.dataset.side_effect = publish_dataset
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}), TestClient(app) as client:
            try:
                progress = client.get("/api/performance").json()
                self.assertEqual(progress["arize_publication"]["status"], "running")
                self.assertEqual(client.post("/api/performance/benchmark", headers=self.headers).status_code, 409)
            finally:
                release.set()
            client.portal.call(self.wait_for_startup_publication)
            result = client.get("/api/performance").json()

        self.sdk.assert_called_once_with(api_key="evaluation-key")
        self.assertEqual(len(self.dataset.call_args.args[2]["examples"]), 2)
        self.assertEqual(result["arize_publication"]["status"], "complete")
        self.assertEqual(result["assets"]["report"]["dataset_id"], "startup-dataset")
        self.assertEqual(len(result["assets"]["report"]["prompts"]), 4)
        self.assertEqual(result["benchmark"]["status"], "pending")
        self.experiment.assert_not_called()

    def test_startup_publication_failure_leaves_backend_available(self):
        with (
            patch.object(application, "publish_bundled_assets", side_effect=RuntimeError("private API detail")),
            self.assertLogs(application.__name__, level="WARNING") as logs,
            TestClient(app) as client,
        ):
            client.portal.call(self.wait_for_startup_publication)
            response = client.get("/api/performance")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["arize_publication"]["status"], "failed")
        self.assertNotIn("private API detail", response.text + str(logs.output))
