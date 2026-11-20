"""Run the bundled governance benchmark as an Arize AX experiment."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from os import getenv
from threading import Lock
from time import perf_counter

from ..agent.evidence import extract_evidence_with_llm
from ..agent.policy import assess_evidence_gaps
from .dataset import DesignCase
from .metrics import evaluate

INPUT_COLUMN = "attributes.input.value"
REFERENCE_COLUMN = "attributes.output.value"
METRICS = (
    "gap_precision", "gap_recall", "gap_set_matches", "risk_tier_matches",
    "rule_coverage", "rule_citation_validity", "source_citation_validity",
)


def _review(case: DesignCase, rules: list[dict]):
    extraction = extract_evidence_with_llm({"rules": rules, "sections": case.sections})
    return assess_evidence_gaps({
        "rules": rules, "declared_tier": case.declared_tier, "evidence": extraction["evidence"],
    })


def _metric(metric, cases, reports, rules):
    from arize.experiments import EvaluationResult

    def score(output):
        if metric == "gap_set_matches":
            return EvaluationResult(score=float(not (output["missed_gaps"] or output["unexpected_gaps"])))
        doc_id = output["doc_id"]
        case = cases[doc_id]
        value = evaluate(reports[doc_id], case.key, case.sections, rules)[metric]
        if value is None:
            return EvaluationResult(label="not_applicable")
        return EvaluationResult(score=float(value))

    return score


def build_dataset(cases: dict[str, DesignCase], rules: list[dict]):
    selected_cases = [cases[doc_id] for doc_id in sorted(cases)]
    examples = [
        {
            INPUT_COLUMN: case.doc_id,
            REFERENCE_COLUMN: json.dumps({
                "expected_gaps": sorted(case.key.not_evidenced_rule_ids),
                "expected_risk_tier": case.key.risk_tier,
                "declared_tier": case.declared_tier,
                "suggested_outcome": case.suggested_outcome,
            }, sort_keys=True),
        }
        for case in selected_cases
    ]
    source_digests = [case.source_digest for case in selected_cases]
    snapshot = json.dumps([examples, source_digests, rules], sort_keys=True)
    dataset_name = f"governance-designs-{sha256(snapshot.encode()).hexdigest()[:16]}"
    return {"name": dataset_name, "examples": examples}


def run(client, dataset, cases: dict[str, DesignCase], rules: list[dict], model: str, name: str | None, on_phase=None):
    # Keep full reports available to local code evaluators without including quotes in AX outputs.
    reports = {}
    case_results = {}
    progress_lock = Lock()

    def review_design(dataset_row):
        doc_id = dataset_row[INPUT_COLUMN]
        case = cases[doc_id]
        started = perf_counter()
        report = _review(case, rules)
        reports[doc_id] = report
        predicted = {row["rule_id"] for row in report["findings"] if row["status"] == "not_evidenced"}
        expected = case.key.not_evidenced_rule_ids
        case_result = {
            "id": doc_id,
            "expected_tier": case.key.risk_tier,
            "assessed_tier": report["risk_tier"],
            "missed_gaps": len(expected - predicted),
            "unexpected_gaps": len(predicted - expected),
            "duration_seconds": round(perf_counter() - started, 2),
        }
        with progress_lock:
            case_results[doc_id] = case_result
            if on_phase:
                on_phase(f"Reviewed {len(case_results)} of {len(cases)} designs")
        return {
            "doc_id": doc_id,
            "risk_tier": report["risk_tier"],
            "predicted_gaps": sorted(predicted),
            "missed_gaps": sorted(expected - predicted),
            "unexpected_gaps": sorted(predicted - expected),
        }

    mode = "full_document" if getenv("EVIDENCE_RETRIEVAL_MODE") == "full_document" else "passages"
    experiment_name = name or f"{mode}-{datetime.now(UTC):%Y%m%d-%H%M%S-%f}"
    if on_phase:
        on_phase(f"Reviewing {len(cases)} designs and scoring results")
    _, results = client.experiments.run(
        name=experiment_name,
        dataset=dataset.id,
        task=review_design,
        evaluators={metric: _metric(metric, cases, reports, rules) for metric in METRICS},
        concurrency=2,
        timeout=360,
        exit_on_error=True,
        force_http=True,
        dry_run=True,
        dry_run_count=len(cases),
        metadata={"retrieval_mode": mode, "model": model},
    )
    mean_scores = {}
    for metric in METRICS:
        scores = results[f"eval.{metric}.score"].dropna()
        mean_scores[metric] = None if scores.empty else float(scores.mean())
    return {
        "dataset_id": dataset.id,
        "experiment_name": experiment_name,
        "retrieval_mode": mode,
        "model": model,
        "case_count": len(results),
        "mean_scores": mean_scores,
        "cases": [case_results[doc_id] for doc_id in sorted(case_results)],
    }, results


def publish_experiment(client, report: dict, results):
    from arize.experiments.types import EvaluationResultFieldNames, ExperimentTaskFieldNames

    columns = ["example_id", "output"]
    evaluators = {}
    for metric in METRICS:
        score = f"eval.{metric}.score"
        label = f"eval.{metric}.label"
        # Pass the documented task and evaluator fields. The runner also returns trace and execution metadata.
        columns.extend((score, label))
        evaluators[metric] = EvaluationResultFieldNames(score=score, label=label)
    return client.experiments.create(
        name=report["experiment_name"],
        dataset=report["dataset_id"],
        experiment_runs=results.loc[:, columns],
        task_fields=ExperimentTaskFieldNames(example_id="example_id", output="output"),
        evaluator_columns=evaluators,
        force_http=True,
    )
