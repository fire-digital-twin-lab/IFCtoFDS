"""Typed models for P4c grid-sensitivity study evidence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ifc_to_fds.domain.bim.bounding_box import BoundingBox

from .mesh_plan_models import ResolvedLocalMeshPlan


SensitivityLevel = Literal["COARSE", "MEDIUM", "FINE"]
TrendKind = Literal["FLAT", "MONOTONIC", "OSCILLATORY", "PLATEAU_OR_UNRESOLVED"]
ChangeTrend = Literal[
    "DECREASING_CHANGE",
    "INCREASING_CHANGE",
    "UNCHANGED_CHANGE_MAGNITUDE",
]


class GridSensitivityPlanRequest(BaseModel):
    """Three explicit mesh levels over one reviewed local source region."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    source_vehicle_index: int = Field(default=0, ge=0)
    local_region: BoundingBox
    refinement_ratios: tuple[int, int, int] = (2, 3, 4)

    @field_validator("refinement_ratios")
    @classmethod
    def validate_ratios(cls, value: tuple[int, int, int]) -> tuple[int, int, int]:
        if any(ratio < 2 for ratio in value):
            raise ValueError("Grid-sensitivity refinement ratios must all be >= 2")
        if not (value[0] < value[1] < value[2]):
            raise ValueError(
                "Grid-sensitivity refinement ratios must be strictly increasing "
                "from COARSE to MEDIUM to FINE"
            )
        return value


class GridSensitivityCasePlan(BaseModel):
    """One resolved mesh level in a three-level sensitivity plan."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    level: SensitivityLevel
    refinement_ratio: int = Field(ge=2)
    local_dx_m: float = Field(gt=0)
    mesh_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mesh_plan: ResolvedLocalMeshPlan


class ResolvedGridSensitivityPlan(BaseModel):
    """Comparable coarse/medium/fine plans; not a convergence verdict."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    source_vehicle_index: int
    requested_local_region: BoundingBox
    scenario_invariant_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[GridSensitivityCasePlan] = Field(min_length=3, max_length=3)
    status: Literal["INCONCLUSIVE"] = "INCONCLUSIVE"
    scientific_interpretation: Literal["STUDY_PLAN_SOFTWARE_VERIFIED_ONLY"] = (
        "STUDY_PLAN_SOFTWARE_VERIFIED_ONLY"
    )

    @model_validator(mode="after")
    def validate_case_order(self) -> "ResolvedGridSensitivityPlan":
        expected = ["COARSE", "MEDIUM", "FINE"]
        if [case.level for case in self.cases] != expected:
            raise ValueError("Grid-sensitivity cases must be ordered COARSE/MEDIUM/FINE")
        ratios = [case.refinement_ratio for case in self.cases]
        if not (ratios[0] < ratios[1] < ratios[2]):
            raise ValueError("Resolved refinement ratios must be strictly increasing")
        dx = [case.local_dx_m for case in self.cases]
        if not (dx[0] > dx[1] > dx[2]):
            raise ValueError("Local dx must strictly decrease toward FINE")
        return self


class GridSensitivityObservation(BaseModel):
    """One scalar observable with enough provenance for cross-grid comparison."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    metric_id: str = Field(min_length=1)
    quantity: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    value: float
    aggregation: Literal[
        "POINT",
        "MAX",
        "MIN",
        "MEAN",
        "FINAL",
        "TIME_TO_THRESHOLD",
        "INTEGRAL",
    ]
    location_m: tuple[float, float, float] | None = None
    time_window_s: tuple[float, float] | None = None
    source_artifact: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("time_window_s")
    @classmethod
    def validate_time_window(
        cls, value: tuple[float, float] | None
    ) -> tuple[float, float] | None:
        if value is not None and value[0] > value[1]:
            raise ValueError("Observation time window must be ordered start <= stop")
        return value


class GridSensitivityCaseResult(BaseModel):
    """Observed outputs for one mesh level."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    level: SensitivityLevel
    refinement_ratio: int = Field(ge=2)
    local_dx_m: float = Field(gt=0)
    scenario_invariant_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fds_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observations: list[GridSensitivityObservation] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_metrics(self) -> "GridSensitivityCaseResult":
        ids = [observation.metric_id for observation in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate metric_id in one grid-sensitivity case")
        return self


class MetricSensitivityEvidence(BaseModel):
    """Descriptive changes only; no universal convergence threshold."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    metric_id: str
    quantity: str
    unit: str
    aggregation: str
    coarse_value: float
    medium_value: float
    fine_value: float
    coarse_to_medium_delta: float
    medium_to_fine_delta: float
    coarse_to_medium_abs_delta: float = Field(ge=0)
    medium_to_fine_abs_delta: float = Field(ge=0)
    coarse_to_medium_relative_to_finer: float | None = Field(default=None, ge=0)
    medium_to_fine_relative_to_finer: float | None = Field(default=None, ge=0)
    trend: TrendKind
    change_trend: ChangeTrend
    relative_change_denominator: Literal["ABSOLUTE_FINER_VALUE"] = (
        "ABSOLUTE_FINER_VALUE"
    )


class GridSensitivityStudyEvidence(BaseModel):
    """Fail-closed P4c1 result until reviewed acceptance criteria exist."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["INCONCLUSIVE"] = "INCONCLUSIVE"
    reason: str
    scenario_invariant_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    comparison_status: Literal["COMPARABLE"] = "COMPARABLE"
    acceptance_policy: Literal["NOT_DEFINED"] = "NOT_DEFINED"
    numerical_uncertainty_status: Literal["NOT_ESTIMATED"] = "NOT_ESTIMATED"
    cases: list[GridSensitivityCaseResult] = Field(min_length=3, max_length=3)
    metrics: list[MetricSensitivityEvidence] = Field(min_length=1)
