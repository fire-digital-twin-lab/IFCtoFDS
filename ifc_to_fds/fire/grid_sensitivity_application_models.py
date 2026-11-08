"""Typed readiness evidence for application-relevant P4c2b grid studies."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReadinessStatus = Literal["READY", "NOT_READY"]


class ApplicationGridStudyReadiness(BaseModel):
    """Fail-closed reference/source readiness evidence for P4c2b execution."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    status: ReadinessStatus
    reason: str = Field(min_length=1)
    reference_case: str = Field(min_length=1)
    reference_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    approval_status: str | None = None
    reviewer: str | None = None
    reference_schema_version: str | None = None
    current_schema_version: str = Field(min_length=1)
    simulation_domain: dict[str, float] | None = None
    source_count: int = Field(default=0, ge=0)
    sources_verified: bool = False
    mapping_acceptance: str | None = None
    output_complete: bool | None = None
    blockers: list[str] = Field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "READY"
