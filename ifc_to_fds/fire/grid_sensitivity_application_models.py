"""Typed readiness evidence for application-relevant P4c2b grid studies."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    @model_validator(mode="after")
    def validate_readiness_consistency(self) -> "ApplicationGridStudyReadiness":
        if self.status == "READY":
            if self.blockers:
                raise ValueError("READY readiness cannot contain blockers")
            if not self.sources_verified or self.source_count < 1:
                raise ValueError("READY readiness requires verified external sources")
            if self.reference_schema_version != self.current_schema_version:
                raise ValueError("READY readiness requires current reference schema")
            if self.simulation_domain is None:
                raise ValueError("READY readiness requires an approved simulation domain")
            if self.mapping_acceptance != "MAPPING_VERIFIED":
                raise ValueError("READY readiness requires MAPPING_VERIFIED reference")
            if self.output_complete is not True:
                raise ValueError("READY readiness requires complete reference output")
        elif not self.blockers:
            raise ValueError("NOT_READY readiness requires at least one blocker")
        return self

    @property
    def ready(self) -> bool:
        return self.status == "READY"
