"""Evaluate the bundled design benchmark in Arize AX or score an exported review."""

import argparse
import json
from datetime import date
from hashlib import sha256
from os import getenv
from pathlib import Path
from typing import Callable

from .agent.documents import parse_document
from .evaluation.dataset import load_dataset
from .evaluation.experiment import build_dataset, publish_experiment, publish_experiment_scores, run
from .evaluation.judge import judge
from .evaluation.metrics import AnswerKey, evaluate
from .evaluation.publish import arize_api_key, connect_arize, publication_step, publish_assets
from .performance import save_report
from .standards_store.catalog import load_rules


def _score_export(args):
    review = json.loads(args.review.read_text())
    key = AnswerKey.model_validate_json(args.answer_key.read_bytes())
    sections = parse_document(args.source.name, args.source.read_bytes())
    supporting_documents = {}
    for path in args.supporting_document:
        payload = path.read_bytes()
        supporting_documents[sha256(payload).hexdigest()] = parse_document(path.name, payload)
    rules = load_rules(date.fromisoformat(review["as_of"]), review["document_type"])
    scores = evaluate(review, key, sections, rules, supporting_documents)
    if args.judge:
        scores["llm_judge"] = judge(review, key, sections, supporting_documents)
    return scores


def missing_benchmark_settings() -> list[str]:
    missing = [key for key in ("ARIZE_SPACE_ID", "OPENAI_API_KEY") if not getenv(key, "").strip()]
    if not arize_api_key():
        missing.append("ARIZE_EVAL_API_KEY or ARIZE_API_KEY")
    return missing


def fixture_summary(cases, rules):
    return {
        "case_count": len(cases),
        "rule_count": len(rules),
        "expected_finding_count": sum(len(case.key.not_evidenced_rule_ids) for case in cases.values()),
        "design_ids": list(cases),
    }


def run_benchmark(cases, rules, available_case_count, name=None, on_phase: Callable[[str], None] | None = None):
    space = getenv("ARIZE_SPACE_ID", "").strip()
    model = getenv("OPENAI_MODEL", "gpt-6-luna")
    client = connect_arize(arize_api_key(), on_phase)
    dataset, assets = publish_assets(client, space, build_dataset(cases, rules), model, on_phase=on_phase)
    summary, results = run(client, dataset, cases, rules, model, name, on_phase=on_phase)
    output = {**assets, **summary, "available_case_count": available_case_count}
    if on_phase:
        on_phase("Saving benchmark scores")
    save_report("benchmark", output)
    with publication_step("Creating the Arize experiment", on_phase):
        experiment = publish_experiment(client, summary, results)
    output["experiment_id"] = experiment.id
    output["experiment_scores_published"] = False
    save_report("benchmark", output)
    with publication_step("Attaching scores to the Arize experiment", on_phase):
        publish_experiment_scores(client, experiment.id, space, results)
    output["experiment_scores_published"] = True
    if on_phase:
        on_phase("Saving the Arize publication status")
    save_report("benchmark", output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path, nargs="?", help="Legacy mode: exported JSON decision record.")
    parser.add_argument("source", type=Path, nargs="?", help="Legacy mode: original source document.")
    parser.add_argument("answer_key", type=Path, nargs="?", help="Legacy mode: human answer key JSON.")
    parser.add_argument("--supporting-document", type=Path, action="append", default=[],
                        help="Legacy mode: original file for a supporting citation. Repeat as needed.")
    parser.add_argument("--judge", action="store_true", help="Legacy mode: also use the OpenAI judge.")
    parser.add_argument("--case", action="append", help="Run a design ID such as SD-01. Repeat to select multiple.")
    parser.add_argument("--experiment", help="Custom name for the Arize AX experiment.")
    parser.add_argument("--validate-only", action="store_true", help="Check the bundled files without API calls.")
    args = parser.parse_args()
    inputs = (args.review, args.source, args.answer_key)
    if any(inputs):
        if not all(inputs):
            parser.error("Pass the exported review, source document, and JSON answer key together.")
        if args.case or args.experiment or args.validate_only:
            parser.error("Bundled benchmark options cannot be used with an exported review.")
        print(json.dumps(_score_export(args), indent=2))
        return
    if args.judge or args.supporting_document:
        parser.error("--judge and --supporting-document require an exported review.")

    cases, rules = load_dataset()
    all_fixtures = fixture_summary(cases, rules)
    available_case_count = len(cases)
    if args.case:
        unknown = sorted(set(args.case) - cases.keys())
        if unknown:
            parser.error(f"Unknown design ID: {', '.join(unknown)}.")
        cases = {doc_id: case for doc_id, case in cases.items() if doc_id in args.case}
    if args.validate_only:
        output = fixture_summary(cases, rules)
        save_report("fixtures", {**output, "available_case_count": available_case_count})
    else:
        missing = missing_benchmark_settings()
        if missing:
            parser.error(f"Set these environment variables before running an experiment: {', '.join(missing)}.")
        save_report("fixtures", {**all_fixtures, "available_case_count": available_case_count})
        output = run_benchmark(cases, rules, available_case_count, name=args.experiment)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
