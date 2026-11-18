"""Determine governance findings and assessed risk from confirmed evidence."""

from .state import State

RISK_TIERS = ("low", "medium", "high")


def assess_evidence_gaps(state: State):
    findings = []
    risk_tier = state["declared_tier"]
    for rule in state["rules"]:
        evidence = state["evidence"].get(rule["id"])
        gap_risk = None if evidence else rule["gap_risk"]
        if gap_risk and RISK_TIERS.index(gap_risk) > RISK_TIERS.index(risk_tier):
            risk_tier = gap_risk
        findings.append({
            "rule_id": rule["id"],
            "standard": rule["standard"],
            "effective_date": rule["effective_date"],
            "rule_quote": rule["quote"],
            "evidence_required": rule["evidence_required"],
            "status": "evidence_found" if evidence else "not_evidenced",
            "evidence": evidence,
            "gap_risk": gap_risk,
        })
    return {"findings": findings, "risk_tier": risk_tier}
