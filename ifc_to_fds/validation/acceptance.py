"""Explicit evidence gates; absence of findings is not a pass."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from ifc_to_fds.core.canonical import SCHEMA_VERSION


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class AcceptanceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GateResult(BaseModel):
    status: GateStatus = GateStatus.NOT_RUN
    required: bool = True
    reason: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


class AuditConfig(BaseModel):
    surface_tolerance_m: float = Field(0.001, gt=0, allow_inf_nan=False)
    relative_volume_tolerance: float = Field(0.001, ge=0, lt=1, allow_inf_nan=False)
    min_solid_iou: float = Field(0.999, gt=0, le=1, allow_inf_nan=False)
    solver_executable: str | None = None
    solver_version: str = "6.11.1"
    solver_timeout_s: float = Field(120, gt=0, allow_inf_nan=False)


class Finding(BaseModel):
    id: str
    severity: Severity
    category: str
    title: str
    detail: str
    element_id: str = ""
    remediation: str = ""


class AcceptanceReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    status: AcceptanceStatus = AcceptanceStatus.INCONCLUSIVE
    total_elements_checked: int = 0
    matched_count: int = 0
    deviated_count: int = 0
    missing_count: int = 0
    excluded_count: int = 0
    semantic_only_count: int = 0
    findings: list[Finding] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    gates: dict[str, GateResult] = Field(default_factory=dict)
    element_statuses: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)

    def finalize(self):
        required = [g for g in self.gates.values() if g.required]
        if any(g.status == GateStatus.FAIL for g in required) or any(
            f.severity in (Severity.P0, Severity.P1) for f in self.findings
        ):
            self.status = AcceptanceStatus.REJECTED
        elif required and all(
            g.status in (GateStatus.PASS, GateStatus.NOT_APPLICABLE)
            and (g.status != GateStatus.NOT_APPLICABLE or g.reason)
            for g in required
        ):
            self.status = AcceptanceStatus.VERIFIED
        else:
            self.status = AcceptanceStatus.INCONCLUSIVE
        self.summary = {
            s.value: sum(f.severity == s for f in self.findings) for s in Severity
        }
        return self

    def to_markdown(self):
        def escape(value):
            return str(value).replace("|", r"\|").replace("\n", " ")

        lines = [
            "# IFCtoFDS Conversion Acceptance Report",
            "",
            f"**Overall Verdict:** `{self.status.value}`",
            "",
            f"Accounted elements: {self.total_elements_checked}; matched solids: {self.matched_count}",
            "",
            "| Gate | Status | Reason |",
            "|---|---|---|",
        ]
        lines += [
            f"| {name} | {g.status.value} | {escape(g.reason)} |"
            for name, g in self.gates.items()
        ]
        lines += ["", "| Severity | Element | Detail |", "|---|---|---|"]
        lines += [
            f"| {f.severity.value} | {escape(f.element_id)} | {escape(f.detail)} |"
            for f in self.findings
        ]
        if not self.findings:
            lines += [
                "",
                "No defects reported by completed checks. See gate statuses for unverified requirements.",
            ]
        return "\n".join(lines) + "\n"
