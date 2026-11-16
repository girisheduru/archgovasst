"""Evaluate an exported review against a source document and a human answer key."""

import argparse
import json
from datetime import date
from pathlib import Path

from .agent.documents import parse_document
from .evaluation.judge import judge
from .evaluation.metrics import AnswerKey, evaluate
from .standards_store.catalog import load_rules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("answer_key", type=Path)
    parser.add_argument("--judge", action="store_true", help="Also send evaluation inputs to OpenAI.")
    args = parser.parse_args()
    review = json.loads(args.review.read_text())
    key = AnswerKey.model_validate_json(args.answer_key.read_bytes())
    sections = parse_document(args.source.name, args.source.read_bytes())
    rules = load_rules(date.fromisoformat(review["as_of"]), review["document_type"])
    scores = evaluate(review, key, sections, rules)
    if args.judge:
        scores["llm_judge"] = judge(review, key, sections)
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
