"""Versioned, mode-specific public result contracts for background jobs.

This module guards the JSON/API trust boundary. It checks structural and
logical consistency; it does NOT claim to independently certify CFD results
or the bytes of every scientific artifact.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator

from ifc_to_fds.core.canonical import SCHEMA_VERSION
from ifc_to_fds.results import ARTIFACTS


class ResultShape(BaseModel):
    # Keep additive metadata compatible while validating every field that
    # can influence scientific acceptance or downloadable artifact URLs.
    model_config = ConfigDict(extra="allow")


class ArtifactDescriptor(ResultShape):
    filename: str = Field(min_length=1)


class GateSummary(ResultShape):
    status: Literal["PASS", "FAIL", "NOT_RUN", "INCONCLUSIVE", "NOT_APPLICABLE"]
    required: StrictBool
    reason: str
    reason_code: str = ""


class ConversionResult(ResultShape):
    schema_version: str
    status: Literal["MAPPING_VERIFIED", "REJECTED", "INCONCLUSIVE"]
    mapping_status: Literal["MAPPING_VERIFIED", "REJECTED", "INCONCLUSIVE"]
    simulation_status: Literal["REJECTED", "INCONCLUSIVE"]
    output_complete: StrictBool
    source_filename: str = Field(min_length=1)
    profile: Literal["mapping", "research-basement", "simulation", "geometry-fidelity"]
    coverage: dict[str, Any]
    timings: dict[str, Any]
    gates: dict[str, GateSummary]
    findings: list[dict[str, Any]]
    findings_count: int = Field(ge=0, strict=True)
    blocker_count: int = Field(ge=0, strict=True)
    research: dict[str, Any]
    artifacts: dict[str, ArtifactDescriptor]

    @model_validator(mode="after")
    def check_acceptance(self) -> "ConversionResult":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("Conversion result schema version is unsupported")
        if self.findings_count != len(self.findings):
            raise ValueError("Conversion findings_count differs from findings list")
        if self.output_complete != (self.mapping_status == "MAPPING_VERIFIED"):
            raise ValueError("Conversion output_complete contradicts mapping_status")
        actual_blockers = sum(
            gate.required and gate.status not in ("PASS", "NOT_APPLICABLE")
            for gate in self.gates.values()
        )
        if self.blocker_count != actual_blockers:
            raise ValueError("Conversion blocker_count contradicts gate statuses")
        if self.status not in (self.mapping_status, self.simulation_status):
            raise ValueError("Overall acceptance status contradicts mapping/simulation")
        if self.mapping_status == "MAPPING_VERIFIED":
            mandatory = {
                "syntax", "source_inventory", "traceability", "scope",
                "geometry", "representation", "domain",
            }
            missing_gates = mandatory - self.gates.keys()
            if missing_gates:
                raise ValueError(f"Verified mapping is missing gates: {sorted(missing_gates)}")
            simulation_gates = {
                "solver", "effective_geometry", "physics",
                "scenario", "mesh_resolution", "operational_model",
            }
            required_mapping = [
                gate for name, gate in self.gates.items()
                if gate.required and name not in simulation_gates
            ]
            if not required_mapping or any(
                gate.status not in ("PASS", "NOT_APPLICABLE")
                or (gate.status == "NOT_APPLICABLE" and not gate.reason.strip())
                for gate in required_mapping
            ):
                raise ValueError("Verified mapping contradicts required mapping gate evidence")
            if any(
                finding.get("severity") in ("P0", "P1")
                and finding.get("verification_level", "mapping") == "mapping"
                for finding in self.findings
            ):
                raise ValueError("Verified mapping contains blocking scientific findings")
            missing = {"fds", "manifest", "report", "geometry"} - self.artifacts.keys()
            if missing:
                raise ValueError(f"Verified mapping is missing artifacts: {sorted(missing)}")
        return self


class ScenarioResult(ResultShape):
    status: Literal["COMPLETED"]
    verdict: Literal["FAIL", "INCONCLUSIVE"]
    verdict_reason: str = Field(min_length=1)
    mesh_status: Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN", "NOT_APPLICABLE"]
    physics_status: Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN", "NOT_APPLICABLE"]
    simulation_status: Literal["NOT_RUN"]
    peak_hrr_mw: float = Field(ge=0, allow_inf_nan=False)
    evidence: dict[str, Any]
    artifacts: dict[str, ArtifactDescriptor]
    scenario_id: str = Field(min_length=1)
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fds_file: Literal["scenario.fds"]

    @model_validator(mode="after")
    def check_verdict(self) -> "ScenarioResult":
        fails = self.mesh_status == "FAIL" or self.physics_status == "FAIL"
        if fails != (self.verdict == "FAIL"):
            raise ValueError("Scenario verdict contradicts mesh/physics gates")
        if "scenario_fds" not in self.artifacts:
            raise ValueError("Scenario result is missing scenario_fds")
        if not isinstance(self.evidence.get("physics"), dict):
            raise ValueError("Scenario physics evidence is missing")
        digest = self.evidence.get("fds_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            c not in "0123456789abcdef" for c in digest
        ):
            raise ValueError("Scenario FDS evidence hash is missing or malformed")
        return self


class PreviewResult(ResultShape):
    status: Literal["PREVIEW_ONLY"]
    verification: Literal["NOT_RUN"]
    display_linear_deflection_m: float = Field(gt=0, allow_inf_nan=False)
    total_elements: int = Field(ge=0, strict=True)
    rendered_elements: int = Field(ge=0, strict=True)
    failed_elements: int = Field(ge=0, strict=True)
    bounds: dict[str, Any] | None
    sources: list[dict[str, Any]]
    storeys: list[dict[str, Any]]
    artifacts: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def check_preview(self) -> "PreviewResult":
        if self.rendered_elements > self.total_elements or self.failed_elements > self.total_elements:
            raise ValueError("Preview counts exceed total_elements")
        if set(self.artifacts) - {"geometry", "mep"}:
            raise ValueError("Preview artifact keys are unsupported")
        return self


class InventoryResult(ResultShape):
    # Inventory is intentionally status-less; it never implies validation.
    total_elements: int = Field(ge=0, strict=True)
    storeys: list[str]
    storey_references: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    research: dict[str, Any]


_MODELS: dict[str, type[BaseModel]] = {
    "convert": ConversionResult,
    "scenario": ScenarioResult,
    "preview": PreviewResult,
    "inventory": InventoryResult,
}


def validate_job_result(mode: str, result: Any) -> dict[str, Any]:
    """Validate a persisted/public result without assigning acceptance.

    Unknown modes, invalid scientific status combinations, malformed payloads,
    forged artifact names and unsupported outputs fail closed. This function
    returns the original document (no destructive re-serialization).
    """
    if not isinstance(result, dict):
        raise ValueError("result.json must be a JSON object")
    model_type = _MODELS.get(mode)
    if model_type is None:
        raise ValueError(f"Unsupported result mode: {mode!r}")
    try:
        model_type.model_validate(result)
    except ValidationError as exc:
        # Avoid leaking arbitrary user-controlled content into error messages.
        fields = sorted({str(err.get("loc", ("result",))[0]) for err in exc.errors()})
        raise ValueError(f"Invalid {mode} result fields: {', '.join(fields)}") from exc

    if mode in ("convert", "scenario"):
        artifacts = result["artifacts"]
        for name, artifact in artifacts.items():
            filename = ARTIFACTS.get(name)
            if filename is None or artifact["filename"] != filename:
                raise ValueError(f"Invalid {mode} artifact descriptor: {name!r}")

    if mode == "inventory" and "status" in result:
        raise ValueError("Inventory cannot claim a mapping or simulation status")

    return result
