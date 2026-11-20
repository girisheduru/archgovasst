"""Run the bundled governance benchmark as an Arize AX experiment."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from math import isfinite
from os import getenv
from threading import Lock
from time import perf_counter

from ..agent.evidence import extract_evidence_with_llm
from ..agent.policy import assess_evidence_gaps
from .dataset import DesignCase
from .metrics import evaluate
from .prompt_checks import PROMPTS, check_prompt

INPUT_COLUMN = "attributes.input.value"
REFERENCE_COLUMN = "attributes.output.value"
METRICS = (
    "gap_precision", "gap_recall", "gap_set_matches", "risk_tier_matches",
    "rule_coverage", "rule_citation_validity", "source_citation_validity",
)
PROMPT_METRICS = {f"prompt_{name}": name for name in PROMPTS}


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
    prompt_evals = {prompt: {"passed": 0, "failed": 0, "errors": 0} for prompt in PROMPTS}
    progress_lock = Lock()
    completed_prompt_checks = 0

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

    def prompt_evaluator(prompt):
        from arize.experiments import EvaluationResult

        def score(output):
            nonlocal completed_prompt_checks
            doc_id = output["doc_id"]
            verdict = check_prompt(prompt, cases[doc_id], rules, reports[doc_id], model)
            with progress_lock:
                count = {"pass": "passed", "fail": "failed", "error": "errors"}[verdict]
                prompt_evals[prompt][count] += 1
                completed_prompt_checks += 1
                if on_phase:
                    on_phase(f"Evaluated {completed_prompt_checks} of {len(cases) * len(PROMPTS)} prompt responses")
            if verdict == "error":
                return EvaluationResult(label=verdict)
            return EvaluationResult(label=verdict, score=float(verdict == "pass"))

        return score

    mode = "full_document" if getenv("EVIDENCE_RETRIEVAL_MODE") == "full_document" else "passages"
    experiment_name = name or f"{mode}-{datetime.now(UTC):%Y%m%d-%H%M%S-%f}"
    if on_phase:
        on_phase(f"Reviewing {len(cases)} designs and scoring results")
    _, results = client.experiments.run(
        name=experiment_name,
        dataset=dataset.id,
        task=review_design,
        evaluators={
            **{metric: _metric(metric, cases, reports, rules) for metric in METRICS},
            **{metric: prompt_evaluator(prompt) for metric, prompt in PROMPT_METRICS.items()},
        },
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
        "prompt_evals": prompt_evals,
        "cases": [case_results[doc_id] for doc_id in sorted(case_results)],
    }, results


def prompt_experiment_name(benchmark_name: str, prompt: str) -> str:
    name = f"{prompt.replace('_', '-')}-{benchmark_name}"
    if len(name) <= 255:
        return name
    return f"{name[:238]}-{sha256(name.encode()).hexdigest()[:16]}"


def publish_experiment(client, report: dict, results, *, prompt: str | None = None):
    from arize.experiments.types import ExperimentTaskFieldNames

    if prompt is None:
        runs = results.loc[:, ["example_id", "output"]]
    else:
        score_column = f"eval.prompt_{prompt}.score"
        verdicts = {1.0: "pass", 0.0: "fail"}
        runs = [
            {"example_id": row["example_id"], "output": {"verdict": verdicts.get(row.get(score_column), "error")}}
            for row in results.to_dict(orient="records")
        ]
    return client.experiments.create(
        name=report["experiment_name"],
        dataset=report["dataset_id"],
        experiment_runs=runs,
        task_fields=ExperimentTaskFieldNames(example_id="example_id", output="output"),
        force_http=True,
    )


def publish_experiment_scores(client, experiment_id: str, space: str, results, *, prompt: str | None = None):
    from arize.experiments.types import AnnotateRecordInput, AnnotationInput

    scores_by_example = {row["example_id"]: row for row in results.to_dict(orient="records")}
    runs = client.experiments.list_runs(experiment=experiment_id, limit=len(scores_by_example)).experiment_runs or []
    if len(runs) != len(scores_by_example) or {run.example_id for run in runs if run.id} != scores_by_example.keys():
        raise ValueError("Arize did not return a run ID for every scored dataset example.")
    annotations = []
    score_names = set()
    metrics = (f"prompt_{prompt}",) if prompt else (*METRICS, *PROMPT_METRICS)
    for run in runs:
        row = scores_by_example[run.example_id]
        values = []
        for metric in metrics:
            score = row.get(f"eval.{metric}.score")
            if score is not None and isfinite(score):
                name = f"governance_{metric}"
                score_names.add(name)
                values.append(AnnotationInput(name=name, score=float(score)))
        if values:
            annotations.append(AnnotateRecordInput(record_id=run.id, values=values))
    for name in sorted(score_names):
        configs = client.annotation_configs.list(name=name, space=space).annotation_configs or []
        config = next((item for item in configs if item.name == name), None)
        if config is None:
            client.annotation_configs.create_continuous(name=name, space=space, minimum_score=0, maximum_score=1)
        elif (getattr(config, "minimum_score", None), getattr(config, "maximum_score", None)) != (0, 1):
            raise ValueError("An existing Arize score annotation has an incompatible range or type.")
    if annotations:
        client.experiments.annotate_runs(experiment=experiment_id, annotations=annotations)
