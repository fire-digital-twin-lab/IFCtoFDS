"""Acceptance Gate and Compliance Reporting.

Evaluates findings across Tier 1, 2, and 3 validation passes against strict
acceptance criteria, blocking acceptance if any P0 or P1 defect is unmitigated.
"""

from enum import Enum
from typing import Dict, List
from pydantic import BaseModel, Field


class Severity(str, Enum):
    P0 = "P0"  # Critical blocker: missing elements, lost openings, corrupted model
    P1 = "P1"  # Major defect: coordinate drift, missing MEP connectivity
    P2 = "P2"  # Warning: non-manifold edges, high deviation
    P3 = "P3"  # Informational notice


class Finding(BaseModel):
    id: str
    severity: Severity
    category: str
    title: str
    detail: str
    element_id: str = ""
    remediation: str = ""


class AcceptanceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class AcceptanceReport(BaseModel):
    status: AcceptanceStatus
    total_elements_checked: int
    matched_count: int
    deviated_count: int
    missing_count: int
    excluded_count: int
    semantic_only_count: int
    findings: List[Finding] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)

    def to_markdown(self) -> str:
        md = [
            f"# IFCtoFDS Conversion Acceptance Report",
            f"",
            f"**Overall Verdict:** `{self.status.value}`",
            f"",
            f"## Inventory Metrics",
            f"- **Total Accounted Elements:** {self.total_elements_checked}",
            f"- **Matched Solids:** {self.matched_count}",
            f"- **Deviated / Warning:** {self.deviated_count}",
            f"- **Missing Elements:** {self.missing_count}",
            f"- **Semantic / Non-Obstacle:** {self.semantic_only_count}",
            f"- **Approved Exclusions:** {self.excluded_count}",
            f"",
            f"## Audit Findings",
        ]
        if not self.findings:
            md.append("✅ **No defects detected. Model satisfies all acceptance criteria.**")
        else:
            md.append("| Severity | Category | Title | Detail |")
            md.append("| :--- | :--- | :--- | :--- |")
            for f in self.findings:
                md.append(f"| **{f.severity.value}** | {f.category} | {f.title} | {f.detail} |")

        md.append("")
        return "\n".join(md)
