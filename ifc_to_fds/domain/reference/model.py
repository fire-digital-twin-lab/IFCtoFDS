"""Reference domain models for golden cases, approvals, and intentional deltas."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntentionalDelta(BaseModel):
    element_id: str
    parameter: str
    expected_value: Any
    actual_value: Any
    reason: str
    approved_by: str = ""


class ReferenceApproval(BaseModel):
    case_id: str
    status: str = "DRAFT"  # DRAFT, APPROVED, SUPERSEDED
    approved_by: Optional[str] = None
    approval_date: Optional[str] = None
    rationale: Optional[str] = None


class GoldenReference(BaseModel):
    case_id: str
    schema_version: str = "0.5.0"
    source_signatures: List[Dict[str, Any]] = Field(default_factory=list)
    expected_inventory: Dict[str, Any] = Field(default_factory=dict)
    approval: ReferenceApproval = Field(default_factory=lambda: ReferenceApproval(case_id=""))
    deltas: List[IntentionalDelta] = Field(default_factory=list)


class ReferenceParityResult(BaseModel):
    status: str = "INCONCLUSIVE"
    matched_count: int = 0
    deviated_count: int = 0
    missing_count: int = 0
    unexpected_count: int = 0
    reasons: List[str] = Field(default_factory=list)
