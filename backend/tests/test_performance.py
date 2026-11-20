import unittest
from asyncio import sleep, timeout
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from fastapi.testclient import TestClient

from backend.governance import application, evaluate
from backend.governance.api import performance
from backend.governance.application import app
from backend.governance.evaluation import experiment, publish
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
            evaluate, "run", return_value=({"case_count": 1, "mean_scores": {"gap_precision": 0.8}}, Mock()),
        ))
        self.upload = self.enterContext(patch.object(
            evaluate, "publish_experiment", return_value=SimpleNamespace(id="experiment-id"),
        ))
        self.score_upload = self.enterContext(patch.object(evaluate, "publish_experiment_scores"))
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
        self.assertTrue(result["benchmark"]["report"]["experiment_scores_published"])
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

    def test_smoke_scores_remain_visible_if_arize_rejects_the_experiment_upload(self):
        rejected = RuntimeError("private provider details")
        rejected.status = 422
        rejected.body = '{"detail":[{"loc":["body","experiment_runs",0,"example_id"],"input":"private example"}]}'
        rejected.headers = {"x-request-id": "arize-test-123"}
        self.upload.side_effect = rejected
        with self.assertLogs(performance.__name__, level="ERROR"):
            response = self.client.post("/api/performance/benchmark", headers=self.headers)
        self.assertEqual(response.status_code, 202)

        result = self.client.get("/api/performance").json()
        self.assertEqual(result["job"]["phase"], "Creating the Arize experiment")
        self.assertEqual(result["job"]["status"], "failed")
        self.assertIn("HTTP 422", result["job"]["message"])
        self.assertIn("example_id", result["job"]["message"])
        self.assertIn("arize-test-123", result["job"]["message"])
        self.assertNotIn("private example", result["job"]["message"])
        self.assertEqual(result["benchmark"]["report"]["mean_scores"]["gap_precision"], 0.8)
        self.assertNotIn("experiment_id", result["benchmark"]["report"])

    def test_failed_score_attachment_keeps_the_created_experiment_id(self):
        self.score_upload.side_effect = RuntimeError("private provider details")
        with self.assertLogs(performance.__name__, level="ERROR"):
            response = self.client.post("/api/performance/benchmark", headers=self.headers)
        self.assertEqual(response.status_code, 202)
        result = self.client.get("/api/performance").json()
        self.assertEqual(result["job"]["phase"], "Attaching scores to the Arize experiment")
        self.assertEqual(result["benchmark"]["report"]["experiment_id"], "experiment-id")
        self.assertFalse(result["benchmark"]["report"]["experiment_scores_published"])

    def test_start_requires_token_and_rejects_an_overlapping_run(self):
        url = "/api/performance/benchmark"
        self.assertEqual(self.client.post(url).status_code, 401)
        performance.update_job("running", "Testing concurrent request")
        self.assertEqual(self.client.post(url, headers=self.headers).status_code, 409)
        self.sdk.assert_not_called()

    def test_railway_diagnostics_report_only_configuration_presence(self):
        with patch.dict("os.environ", {
            "RAILWAY_SERVICE_ID": "private-service-id",
            "ARIZE_API_KEY": "",
            "OPENAI_API_KEY": "",
        }):
            response = self.client.get("/api/performance")
        configuration = response.json()["configuration"]
        self.assertTrue(configuration["railway"])
        self.assertEqual(configuration["variables"], {
            "PERFORMANCE_RUN_TOKEN": True,
            "ARIZE_SPACE_ID": True,
            "ARIZE_EVAL_API_KEY": True,
            "ARIZE_API_KEY": False,
            "OPENAI_API_KEY": False,
        })
        self.assertIsNone(response.json()["actions"]["publish"])
        self.assertIn("OPENAI_API_KEY", response.json()["actions"]["benchmark"])
        for value in ("private-service-id", "run-token", "test-space", "evaluation-key"):
            self.assertNotIn(value, response.text)

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

    def test_auth_check_uses_selected_key_and_a_read_only_dataset_lookup(self):
        client = self.sdk.return_value
        client.sdk_config.api_url = "https://api.eu-west-1a.arize.com"
        rejected = RuntimeError("private Arize response")
        rejected.status = 401
        client.datasets.list.side_effect = rejected

        result = publish.check_authentication("test-space", publish.arize_api_key())

        self.sdk.assert_called_once_with(api_key="evaluation-key")
        client.datasets.list.assert_called_once_with(space="test-space", limit=1)
        client.datasets.create.assert_not_called()
        self.assertEqual(result["api_host"], "api.eu-west-1a.arize.com")
        self.assertEqual(result["key_variable"], "ARIZE_EVAL_API_KEY")
        self.assertEqual(result["http_status"], 401)
        self.assertNotIn("private Arize response", str(result))
        self.assertNotIn("evaluation-key", str(result))

    def test_publish_action_reports_arize_permission_error_and_keeps_partial_results(self):
        denied = RuntimeError("private Arize response")
        denied.status = 403
        self.prompt.side_effect = [{"name": "first-template"}, denied]
        with self.assertLogs(performance.__name__, level="ERROR") as logs:
            response = self.client.post("/api/performance/publish", headers=self.headers)
        self.assertEqual(response.status_code, 202)
        response = self.client.get("/api/performance")
        result = response.json()
        self.assertEqual(result["job"]["status"], "failed")
        self.assertIn("governance-passage-extraction", result["job"]["message"])
        self.assertIn("HTTP 403", result["job"]["message"])
        self.assertIn("ARIZE_EVAL_API_KEY", result["job"]["message"])
        self.assertEqual(result["assets"]["report"]["prompts"], [{"name": "first-template"}])
        self.assertNotIn("private Arize response", response.text + str(logs.output))

    def test_publish_action_finishes_arize_calls_before_saving_the_report(self):
        with (
            patch.object(publish, "save_report", side_effect=PermissionError("private storage path")),
            self.assertLogs(performance.__name__, level="ERROR"),
        ):
            response = self.client.post("/api/performance/publish", headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.prompt.call_count, 4)
        result = self.client.get("/api/performance").json()
        self.assertEqual(result["job"]["status"], "failed")
        self.assertIn("Arize assets were published", result["job"]["message"])
        self.assertIn("PERFORMANCE_REPORT_DIR", result["job"]["message"])

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


class ExperimentUploadTests(unittest.TestCase):
    def test_create_uploads_only_example_ids_and_outputs(self):
        client = Mock()
        results = MagicMock()
        with patch.dict("sys.modules", {
            "arize.experiments.types": SimpleNamespace(ExperimentTaskFieldNames=SimpleNamespace),
        }):
            experiment.publish_experiment(client, {
                "dataset_id": "dataset-id", "experiment_name": "smoke",
            }, results)

        arguments = client.experiments.create.call_args.kwargs
        row_selector, columns = results.loc.__getitem__.call_args.args[0]
        self.assertEqual(row_selector, slice(None))
        self.assertEqual(columns, ["example_id", "output"])
        self.assertIs(arguments["experiment_runs"], results.loc.__getitem__.return_value)
        self.assertEqual(arguments["dataset"], "dataset-id")
        self.assertNotIn("evaluator_columns", arguments)

    def test_annotates_by_run_id_and_omits_unavailable_scores(self):
        client = Mock()
        client.experiments.list_runs.return_value.experiment_runs = [
            SimpleNamespace(id="run-2", example_id="example-2"),
            SimpleNamespace(id="run-1", example_id="example-1"),
        ]
        client.annotation_configs.list.return_value.annotation_configs = []
        results = Mock()
        results.to_dict.return_value = [
            {"example_id": example_id, **{f"eval.{metric}.score": score if metric == "gap_precision" else float("nan")
                                         for metric in experiment.METRICS}}
            for example_id, score in (("example-1", 0.9), ("example-2", 0))
        ]
        with patch.dict("sys.modules", {
            "arize.experiments.types": SimpleNamespace(AnnotateRecordInput=SimpleNamespace, AnnotationInput=SimpleNamespace),
        }):
            experiment.publish_experiment_scores(client, "experiment-id", "space-id", results)

        annotations = client.experiments.annotate_runs.call_args.kwargs["annotations"]
        self.assertEqual([(item.record_id, [value.score for value in item.values]) for item in annotations],
                         [("run-2", [0.0]), ("run-1", [0.9])])
        client.annotation_configs.create_continuous.assert_called_once_with(
            name="governance_gap_precision", space="space-id", minimum_score=0, maximum_score=1,
        )
