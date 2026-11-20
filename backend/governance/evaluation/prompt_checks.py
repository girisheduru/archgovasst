"""Exercise each published prompt and grade its response against the Eval Hub rubric."""

import json
from logging import getLogger
from typing import Literal

from openai import OpenAIError
from pydantic import BaseModel

from ..agent.evidence import (
    Extraction, GapGuidance, full_document_payload, gap_guidance_payload, passage_payload,
)
from ..agent.prompts import EVIDENCE_EXTRACTION, GAP_GUIDANCE, PASSAGE_EXTRACTION
from ..agent.retrieval import PASSAGES_PER_RULE, build_passages, rank_passages
from ..providers.openai import parse_response
from .evaluators import prompt_eval_template
from .judge import JUDGE_INSTRUCTIONS, Judgment, review_judge_payload

logger = getLogger(__name__)
PROMPTS = {
    "evidence_extraction": (EVIDENCE_EXTRACTION, Extraction, "Extract evidence from a full design or supporting document."),
    "passage_extraction": (PASSAGE_EXTRACTION, Extraction, "Extract evidence from ranked design passages."),
    "gap_guidance": (GAP_GUIDANCE, GapGuidance, "Suggest what evidence to provide for a rule."),
    "review_judge": (JUDGE_INSTRUCTIONS, Judgment, "Grade an exported review against its source and answer key."),
}


class PromptVerdict(BaseModel):
    verdict: Literal["pass", "fail"]


def _payload(prompt, case, rules, review):
    if prompt == "evidence_extraction":
        return full_document_payload(rules, case.sections)
    if prompt == "passage_extraction":
        passages = build_passages(case.sections)
        ranked = rank_passages(rules, passages) if len(passages) > PASSAGES_PER_RULE else {}
        # Exercise the prompt when the live path would skip it or ranking returns no candidates.
        if not any(ranked.values()):
            indices = list(range(min(len(passages), PASSAGES_PER_RULE)))
            ranked = {rule["id"]: indices for rule in rules}
        return passage_payload(rules, passages, ranked)
    if prompt == "gap_guidance":
        gap = next((rule for rule in rules if rule["id"] in case.key.not_evidenced_rule_ids), None)
        # A design with no labeled gap can still test guidance when no evidence is provided.
        return gap_guidance_payload(gap, case.sections) if gap else gap_guidance_payload(rules[0], {})
    return review_judge_payload(review, case.key, case.sections)


def check_prompt(prompt, case, rules, review, model):
    """Return a verdict without retaining the benchmark's prompt input or response."""
    instructions, schema, _ = PROMPTS[prompt]
    try:
        payload = json.dumps(_payload(prompt, case, rules, review), ensure_ascii=False)
        response = parse_response(model, instructions, payload, schema)
        if response is None:
            return "fail"
        rubric = prompt_eval_template(prompt).format(payload=payload, output=response.model_dump_json())
        assessment = parse_response(
            model, "Apply the rubric and return its pass or fail verdict.", rubric, PromptVerdict,
        )
    except (OpenAIError, ValueError) as exc:
        logger.warning("Prompt check %s on %s could not complete (%s).", prompt, case.doc_id, type(exc).__name__)
        return "error"
    return assessment.verdict if assessment is not None else "error"
