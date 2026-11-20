"""Run the backend application tests and publish a dashboard report."""

import unittest
from os import environ, pathsep
from subprocess import run
from sys import executable, modules
from tempfile import TemporaryDirectory
from time import perf_counter
from types import ModuleType

from .performance import BACKEND_ROOT, report_path, save_report


def run_in_subprocess() -> int:
    # Tests patch process-wide globals and environment variables.
    environment = environ.copy()
    for key in ("ARIZE_API_KEY", "ARIZE_EVAL_API_KEY", "ARIZE_SPACE_ID", "OPENAI_API_KEY", "PERFORMANCE_RUN_TOKEN"):
        environment.pop(key, None)
    environment["PYTHONPATH"] = pathsep.join(filter(None, (str(BACKEND_ROOT), environment.get("PYTHONPATH"))))
    environment["PERFORMANCE_REPORT_DIR"] = str(report_path("tests").parent)
    # Keep dependency configuration discovery and temporary test files outside the running app.
    with TemporaryDirectory(prefix="governance-tests-") as workdir:
        result = run(
            [executable, "-m", "governance.run_application_tests"],
            cwd=workdir, env=environment, timeout=120,
        )
    return result.returncode


def main() -> int:
    if __package__ == "governance":
        # Tests use the repository's backend.governance imports, including on a backend-only deployment.
        backend_package = ModuleType("backend")
        backend_package.__path__ = [str(BACKEND_ROOT)]
        modules["backend"] = backend_package
    suite = unittest.defaultTestLoader.discover(str(BACKEND_ROOT / "tests"))
    started = perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun > 0 and result.wasSuccessful()
    problems = [test for test, _ in result.failures + result.errors] + result.unexpectedSuccesses
    save_report("tests", {
        "passed": passed,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "problem_tests": sorted({getattr(test, "test_case", test).id() for test in problems}),
        "duration_seconds": round(perf_counter() - started, 2),
    })
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
