"""Extract structured evidence and verify quotes against the uploaded design."""

import json
from os import getenv

from openai import OpenAIError
from pydantic import BaseModel

from ..providers.openai import parse_response
from .prompts import EVIDENCE_EXTRACTION
from .state import State


class ModelUnavailable(RuntimeError):
    pass


class Evidence(BaseModel):
    rule_id: str
    source: str
    quote: str


class Extraction(BaseModel):
    evidence: list[Evidence]


def extract(state: State):
    model = getenv("OPENAI_MODEL", "gpt-6-luna")
    response_input = {
        "rules": [
            {
                "id": rule["id"],
                "rule_text": rule["quote"],
                "evidence_required": rule["evidence_required"],
            }
            for rule in state["rules"]
        ],
        "document": state["sections"],
    }
    try:
        extraction = parse_response(
            model, EVIDENCE_EXTRACTION, json.dumps(response_input, ensure_ascii=False), Extraction
        )
    except (OpenAIError, ValueError) as exc:
        raise ModelUnavailable("OpenAI could not extract evidence. Check the backend model and API configuration.") from exc

    if extraction is None:
        raise ModelUnavailable("OpenAI returned no structured evidence.")

    rule_ids = {rule["id"] for rule in state["rules"]}
    evidence = {}
    for item in extraction.evidence:
        quote = " ".join(item.quote.split())
        if item.rule_id in rule_ids and quote and quote in state["sections"].get(item.source, ""):
            evidence.setdefault(item.rule_id, {"source": item.source, "quote": quote})

    return {"evidence": evidence, "extraction_model": model, "stage": "confirm_evidence"}
