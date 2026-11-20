"""Run the bundled governance benchmark as an Arize AX experiment."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from os import getenv
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


def publish_dataset(client, space: str, dataset: dict):
    name = dataset["name"]
    datasets = client.datasets.list(space=space, name=name).datasets
    existing = next((item for item in datasets if item.name == name), None)
    if existing is not None:
        return existing
    return client.datasets.create(space=space, force_http=True, **dataset)


def run(cases: dict[str, DesignCase], rules: list[dict], name: str | None):
    from arize import ArizeClient

    space = getenv("ARIZE_SPACE_ID")
    client = ArizeClient(api_key=getenv("ARIZE_API_KEY"))
    dataset = publish_dataset(client, space, build_dataset(cases, rules))

    # Keep full reports available to local code evaluators without including quotes in AX outputs.
    reports = {}
    case_results = {}

    def review_design(dataset_row):
        doc_id = dataset_row[INPUT_COLUMN]
        case = cases[doc_id]
        started = perf_counter()
        report = _review(case, rules)
        reports[doc_id] = report
        predicted = {row["rule_id"] for row in report["findings"] if row["status"] == "not_evidenced"}
        expected = case.key.not_evidenced_rule_ids
        case_results[doc_id] = {
            "id": doc_id,
            "expected_tier": case.key.risk_tier,
            "assessed_tier": report["risk_tier"],
            "missed_gaps": len(expected - predicted),
            "unexpected_gaps": len(predicted - expected),
            "duration_seconds": round(perf_counter() - started, 2),
        }
        return {
            "doc_id": doc_id,
            "risk_tier": report["risk_tier"],
            "predicted_gaps": sorted(predicted),
            "missed_gaps": sorted(expected - predicted),
            "unexpected_gaps": sorted(predicted - expected),
        }

    mode = "full_document" if getenv("EVIDENCE_RETRIEVAL_MODE") == "full_document" else "passages"
    model = getenv("OPENAI_MODEL", "gpt-6-luna")
    experiment, results = client.experiments.run(
        name=name or f"{mode}-{datetime.now(UTC):%Y%m%d-%H%M%S-%f}",
        dataset=dataset.id,
        task=review_design,
        evaluators={metric: _metric(metric, cases, reports, rules) for metric in METRICS},
        concurrency=2,
        timeout=360,
        exit_on_error=True,
        force_http=True,
        metadata={"retrieval_mode": mode, "model": model},
    )
    mean_scores = {}
    for metric in METRICS:
        scores = results[f"eval.{metric}.score"].dropna()
        mean_scores[metric] = None if scores.empty else float(scores.mean())
    return {
        "dataset_id": dataset.id,
        "experiment_id": experiment.id,
        "retrieval_mode": mode,
        "model": model,
        "case_count": len(results),
        "mean_scores": mean_scores,
        "cases": [case_results[doc_id] for doc_id in sorted(case_results)],
    }
