"""Compare cited findings with the source, standards, and answer key."""

from pydantic import BaseModel

from ..standards_store.models import RiskTier, Rule


class AnswerKey(BaseModel):
    not_evidenced_rule_ids: set[str]
    risk_tier: RiskTier


def evaluate(review: dict, key: AnswerKey, sections: dict, rules: list[dict]):
    findings = review["findings"]
    rule_index = {rule["id"]: Rule.model_validate(rule) for rule in rules}
    ids = [row["rule_id"] for row in findings]
    if not findings or len(ids) != len(set(ids)) or not key.not_evidenced_rule_ids <= rule_index.keys():
        raise ValueError("Use a generated report and an answer key for its standards.")
    gaps = {row["rule_id"] for row in findings if row["status"] == "not_evidenced"}
    correct = len(gaps & key.not_evidenced_rule_ids)
    valid_rule_citations = 0
    for row in findings:
        rule = rule_index.get(row["rule_id"])
        if rule and (row["rule_quote"], row["standard"], row["effective_date"]) == (
            rule.quote, rule.standard, rule.effective_date.isoformat()
        ):
            valid_rule_citations += 1
    citations = [row["evidence"] for row in findings if row["evidence"] is not None]
    valid_citations = sum(
        bool(item["quote"]) and item["quote"] in sections.get(item["source"], "")
        for item in citations
    )
    return {
        "gap_precision": correct / len(gaps) if gaps else None,
        "gap_recall": correct / len(key.not_evidenced_rule_ids) if key.not_evidenced_rule_ids else None,
        "risk_tier_matches": review["risk_tier"] == key.risk_tier,
        "rule_coverage": len(rule_index.keys() & set(ids)) / len(rule_index),
        "rule_citation_validity": valid_rule_citations / len(findings),
        "source_citation_validity": valid_citations / len(citations) if citations else None,
    }
