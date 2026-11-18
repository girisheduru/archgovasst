"""Extract structured evidence and verify quotes against the uploaded design."""

import json
from os import getenv

from openai import OpenAIError
from pydantic import BaseModel

from ..api.tracing import trace_operation
from ..providers.openai import parse_response
from .prompts import EVIDENCE_EXTRACTION, PASSAGE_EXTRACTION
from .retrieval import PASSAGES_PER_RULE, build_passages, rank_passages
from .state import State


class ModelUnavailable(RuntimeError):
    pass


class Evidence(BaseModel):
    rule_id: str
    source: str
    quote: str


class Extraction(BaseModel):
    evidence: list[Evidence]


def _model_rule(rule):
    return {
        "id": rule["id"],
        "rule_text": rule["quote"],
        "evidence_required": rule["evidence_required"],
    }


def _extract_quotes(model, instructions, response_input, allowed_passages):
    try:
        extraction = parse_response(
            model, instructions, json.dumps(response_input, ensure_ascii=False), Extraction
        )
    except (OpenAIError, ValueError) as exc:
        raise ModelUnavailable("OpenAI could not extract evidence. Check the backend model and API configuration.") from exc

    if extraction is None:
        raise ModelUnavailable("OpenAI returned no structured evidence.")

    evidence = {}
    for item in extraction.evidence:
        quote = " ".join(item.quote.split())
        if quote and any(
            quote in passage.get(item.source, "") for passage in allowed_passages.get(item.rule_id, [])
        ):
            evidence.setdefault(item.rule_id, {"source": item.source, "quote": quote})
    return evidence


def _extract_from_passages(model, rules, passages):
    try:
        with trace_operation("design.rank_passages", "RETRIEVER", {
            "retrieval.rule_count": len(rules), "retrieval.passage_count": len(passages),
        }):
            ranked = rank_passages(rules, passages)
    except (OpenAIError, ValueError):
        return {}

    selected = sorted({index for indices in ranked.values() for index in indices})
    if not selected:
        return {}
    return _extract_quotes(
        model,
        PASSAGE_EXTRACTION,
        {
            "rules": [
                {**_model_rule(rule), "passage_ids": ranked[rule["id"]]}
                for rule in rules if ranked[rule["id"]]
            ],
            "passages": {index: passages[index] for index in selected},
        },
        {rule_id: [passages[index] for index in indices] for rule_id, indices in ranked.items()},
    )


def extract_evidence_with_llm(state: State):
    model = getenv("OPENAI_MODEL", "gpt-6-luna")
    rules, sections = state["rules"], state["sections"]
    full_document = getenv("EVIDENCE_RETRIEVAL_MODE") == "full_document"
    evidence = {}
    passages = [] if full_document else build_passages(sections)
    if len(passages) > PASSAGES_PER_RULE:
        evidence = _extract_from_passages(model, rules, passages)

    unresolved = [rule for rule in rules if rule["id"] not in evidence]
    if unresolved:
        with trace_operation("design.search_full_document", attributes={
            "retrieval.rule_count": len(unresolved),
            "retrieval.baseline": full_document,
        }):
            evidence.update(_extract_quotes(
                model,
                EVIDENCE_EXTRACTION,
                {"rules": [_model_rule(rule) for rule in unresolved], "document": sections},
                {rule["id"]: [sections] for rule in unresolved},
            ))

    return {"evidence": evidence, "extraction_model": model, "stage": "confirm_evidence"}
