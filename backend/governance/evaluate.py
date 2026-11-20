"""Evaluate an exported review against a source document and a human answer key."""

import argparse
import json
from datetime import date
from hashlib import sha256
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
    parser.add_argument("--supporting-document", type=Path, action="append", default=[],
                        help="Original file for a supporting citation. Repeat for multiple documents.")
    parser.add_argument("--judge", action="store_true", help="Also send evaluation inputs to OpenAI.")
    args = parser.parse_args()
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
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
