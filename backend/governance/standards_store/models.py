from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

RiskTier = Literal["low", "medium", "high"]
DocumentType = Literal["solution_design", "architecture_decision"]


class Rule(BaseModel):
    id: str = Field(min_length=1)
    standard: str = Field(min_length=1)
    effective_date: date
    quote: str = Field(min_length=1)
    evidence_required: str = Field(min_length=1)
    gap_risk: RiskTier
    document_types: list[DocumentType] = Field(min_length=1)
