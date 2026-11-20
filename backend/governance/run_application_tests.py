"""Run the backend application tests and publish a dashboard report."""

import unittest
from time import perf_counter

from .performance import PROJECT_ROOT, save_report


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "backend" / "tests"))
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
