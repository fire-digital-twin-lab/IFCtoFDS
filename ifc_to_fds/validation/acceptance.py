"""Explicit evidence gates; absence of findings is not a pass."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator, ConfigDict
from ifc_to_fds.core.canonical import SCHEMA_VERSION


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class AcceptanceStatus(str, Enum):
    MAPPING_VERIFIED = "MAPPING_VERIFIED"
    SIMULATION_VERIFIED = "SIMULATION_VERIFIED"
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
    model_config = ConfigDict(extra="forbid")
    surface_tolerance_m: float = Field(0.001, gt=0, allow_inf_nan=False)
    relative_volume_tolerance: float = Field(0.001, ge=0, lt=1, allow_inf_nan=False)
    min_solid_iou: float = Field(0.999, gt=0, le=1, allow_inf_nan=False)
    solver_executable: str | None = None
    solver_version: str = "6.11.1"
    solver_timeout_s: float = Field(120, gt=0, allow_inf_nan=False)


class Finding(BaseModel):
    verification_level: str = "mapping"
    id: str
    severity: Severity
    category: str
    title: str
    detail: str
    element_id: str = ""
    remediation: str = ""


class AcceptanceReport(BaseModel):
    requested_level: str = "mapping"
    mapping_status: AcceptanceStatus = AcceptanceStatus.INCONCLUSIVE
    simulation_status: AcceptanceStatus = AcceptanceStatus.INCONCLUSIVE
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

    @model_validator(mode="before")
    @classmethod
    def read_legacy_report(cls, value):
        if isinstance(value, dict) and value.get("schema_version") == "0.3.0":
            value = dict(value)
            value["status"] = "INCONCLUSIVE"
            value["mapping_status"] = "INCONCLUSIVE"
            value["simulation_status"] = "INCONCLUSIVE"
            value["gates"] = {
                **value.get("gates", {}),
                "schema_migration": dict(
                    status="INCONCLUSIVE",
                    reason="Legacy report requires independent audit under schema 0.4",
                ),
            }
        return value

    def finalize(self):
        simulation = {
            "solver",
            "effective_geometry",
            "physics",
            "scenario",
            "mesh_resolution",
            "operational_model",
        }
        required = [
            g for name, g in self.gates.items() if g.required and name not in simulation
        ]
        failed = any(g.status == GateStatus.FAIL for g in required) or any(
            f.severity in (Severity.P0, Severity.P1)
            and f.verification_level == "mapping"
            for f in self.findings
        )
        if failed:
            self.mapping_status = AcceptanceStatus.REJECTED
        elif required and all(
            g.status in (GateStatus.PASS, GateStatus.NOT_APPLICABLE)
            and (g.status != GateStatus.NOT_APPLICABLE or g.reason)
            for g in required
        ):
            self.mapping_status = AcceptanceStatus.MAPPING_VERIFIED
        else:
            self.mapping_status = AcceptanceStatus.INCONCLUSIVE
        sim_failed = any(
            g.status == GateStatus.FAIL
            for name, g in self.gates.items()
            if name in simulation
        )
        self.simulation_status = (
            AcceptanceStatus.REJECTED
            if sim_failed or failed
            else AcceptanceStatus.INCONCLUSIVE
        )
        # Operational/physics/scenario evidence is not implemented by this stage.
        self.status = (
            self.simulation_status
            if self.requested_level == "simulation"
            else self.mapping_status
        )
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
            f"Mapping: `{self.mapping_status.value}`; simulation: `{self.simulation_status.value}`",
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
