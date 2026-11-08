"""Typed execution evidence for P4c2 pinned-FDS grid studies."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .grid_sensitivity_models import (
    GridSensitivityCaseResult,
    GridSensitivityStudyEvidence,
    SensitivityLevel,
)


ExecutionAggregation = Literal["MAX", "MIN", "FINAL"]
SolverExecutionStatus = Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN"]
OutputEvidenceStatus = Literal["PASS", "FAIL", "NOT_EVALUATED"]


class GridSensitivityObservableRequest(BaseModel):
    """One explicit point-DEVC observable to extract from every grid case."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    metric_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    expected_quantity: str = Field(min_length=1)
    expected_unit: str = Field(min_length=1)
    aggregation: ExecutionAggregation
    time_window_s: tuple[float, float] | None = None

    @field_validator("metric_id", "device_id", "expected_quantity", "expected_unit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Observable identifiers, quantity and unit cannot be blank")
        return value

    @field_validator("time_window_s")
    @classmethod
    def validate_time_window(
        cls, value: tuple[float, float] | None
    ) -> tuple[float, float] | None:
        if value is not None and value[0] > value[1]:
            raise ValueError("Observable time window must satisfy start <= stop")
        return value


class GridSensitivityCaseExecutionEvidence(BaseModel):
    """Solver/output provenance for one rendered P4c2 case."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    level: SensitivityLevel
    refinement_ratio: int = Field(ge=2)
    local_dx_m: float = Field(gt=0)
    fds_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    solver_status: SolverExecutionStatus
    output_evidence_status: OutputEvidenceStatus
    reason: str = Field(min_length=1)
    solver_version: str | None = None
    solver_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    configuration_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    run_json_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    stdout_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    stderr_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_files_sha256: dict[str, str] = Field(default_factory=dict)
    result: GridSensitivityCaseResult | None = None

    @model_validator(mode="after")
    def validate_case_provenance(self) -> "GridSensitivityCaseExecutionEvidence":
        if self.result is not None:
            if self.solver_status != "PASS":
                raise ValueError("Case result requires solver_status=PASS")
            required = {
                "solver_version": self.solver_version,
                "solver_sha256": self.solver_sha256,
                "configuration_sha256": self.configuration_sha256,
                "run_json_sha256": self.run_json_sha256,
                "stdout_sha256": self.stdout_sha256,
                "stderr_sha256": self.stderr_sha256,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError(
                    "Accepted case result is missing solver provenance: "
                    + ", ".join(missing)
                )
            if self.result.fds_sha256 != self.fds_sha256:
                raise ValueError("Case result FDS hash differs from execution FDS hash")
        if self.result is not None and not self.output_files_sha256:
            raise ValueError("Accepted case result requires output file checksums")
        for name, digest in self.output_files_sha256.items():
            if not name or "/" in name or "\\" in name:
                raise ValueError("Output evidence keys must be plain file names")
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError(f"Invalid SHA-256 for output artifact {name!r}")
        return self


class ExecutedGridSensitivityStudyEvidence(BaseModel):
    """Fail-closed executed-study evidence; never a convergence acceptance verdict."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["INCONCLUSIVE"] = "INCONCLUSIVE"
    execution_status: Literal["COMPLETE", "INCOMPLETE"]
    reason: str = Field(min_length=1)
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_invariant_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[GridSensitivityCaseExecutionEvidence] = Field(
        min_length=3, max_length=3
    )
    analysis: GridSensitivityStudyEvidence | None = None
    acceptance_policy: Literal["NOT_DEFINED"] = "NOT_DEFINED"
    numerical_uncertainty_status: Literal["NOT_ESTIMATED"] = "NOT_ESTIMATED"

    @model_validator(mode="after")
    def validate_execution_consistency(self) -> "ExecutedGridSensitivityStudyEvidence":
        if [case.level for case in self.cases] != ["COARSE", "MEDIUM", "FINE"]:
            raise ValueError("Executed cases must be ordered COARSE/MEDIUM/FINE")
        complete = all(
            case.solver_status == "PASS"
            and case.output_evidence_status == "PASS"
            and case.result is not None
            for case in self.cases
        )
        if self.execution_status == "COMPLETE" and not complete:
            raise ValueError("COMPLETE execution requires three PASS cases with results")
        if self.execution_status == "INCOMPLETE" and self.analysis is not None:
            raise ValueError("INCOMPLETE execution cannot carry comparative analysis")
        if self.analysis is not None:
            if self.execution_status != "COMPLETE":
                raise ValueError("Analysis requires COMPLETE execution")
            if self.analysis.scenario_invariant_sha256 != self.scenario_invariant_sha256:
                raise ValueError("Analysis scenario fingerprint differs from execution")
        return self
