from typing import TypedDict


class State(TypedDict, total=False):
    filename: str
    document_type: str
    declared_tier: str
    as_of: str
    sections: dict[str, str]
    extraction_model: str
    rules: list[dict]
    evidence: dict[str, dict]
    findings: list[dict]
    risk_tier: str
    stage: str
    audit: list[dict]
