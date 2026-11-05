"""Versioned, mode-specific public result contracts for background jobs.

This module guards the JSON/API trust boundary. It checks structural and
logical consistency; it does NOT claim to independently certify CFD results
or the bytes of every scientific artifact.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator

from ifc_to_fds.core.canonical import SCHEMA_VERSION
from ifc_to_fds.domain.validation.model import (
    NON_WAIVABLE_MAPPING_GATES,
    REQUIRED_MAPPING_GATES,
)
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
        expected_status = (
            self.simulation_status if self.profile == "simulation"
            else self.mapping_status
        )
        if self.status != expected_status:
            raise ValueError(
                "Overall acceptance status contradicts the requested verification profile"
            )
        # Public research metadata is a scientific claim surface too. It
        # must never contradict the finalized outer verdict or the approved
        # reference gate, even when its JSON shape is otherwise valid.
        nested_claims = {
            "status", "verdict", "verification", "mapping_status",
            "simulation_status", "simulation_acceptance",
            "scientific_acceptance", "acceptance_status",
            "verified", "is_verified",
        }
        if nested_claims.intersection(self.research):
            raise ValueError("Research metadata contains unsupported acceptance claims")
        if "profile" in self.research and self.research["profile"] != self.profile:
            raise ValueError("Research metadata profile contradicts result profile")
        if "research_acceptance" in self.research:
            expected_research = (
                self.mapping_status
                if self.profile == "research-basement" else "NOT_RUN"
            )
            if self.research["research_acceptance"] != expected_research:
                raise ValueError("Research acceptance contradicts final mapping verdict")
        if "parity_status" in self.research:
            parity = self.research["parity_status"]
            golden = self.gates.get("golden_reference_parity")
            if parity not in ("PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN"):
                raise ValueError("Unsupported research reference parity status")
            if golden is None and parity != "NOT_RUN":
                raise ValueError("Research parity claims a missing golden gate")
            if golden is not None:
                expected_parity = (
                    "NOT_RUN" if golden.status in ("NOT_APPLICABLE", "NOT_RUN")
                    else golden.status
                )
                # An absent research case yields golden=INCONCLUSIVE but
                # parity=NOT_RUN. This is not permission to hide a failure.
                if parity != expected_parity and not (
                    golden.status == "INCONCLUSIVE" and parity == "NOT_RUN"
                ):
                    raise ValueError("Research parity contradicts golden reference gate")
        if self.profile == "research-basement" and self.mapping_status == "MAPPING_VERIFIED":
            golden = self.gates.get("golden_reference_parity")
            if golden is None or not golden.required or golden.status != "PASS":
                raise ValueError("Research mapping cannot be verified without approved golden parity")
        if self.mapping_status == "MAPPING_VERIFIED":
            missing_gates = REQUIRED_MAPPING_GATES - self.gates.keys()
            if missing_gates:
                raise ValueError(f"Verified mapping is missing gates: {sorted(missing_gates)}")
            if any(
                not self.gates[name].required
                or self.gates[name].status not in ("PASS", "NOT_APPLICABLE")
                or (
                    self.gates[name].status == "NOT_APPLICABLE"
                    and (
                        name in NON_WAIVABLE_MAPPING_GATES
                        or not self.gates[name].reason.strip()
                    )
                )
                for name in REQUIRED_MAPPING_GATES
            ):
                raise ValueError("Verified mapping has incomplete mandatory gate evidence")
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
        physics_evidence = self.evidence.get("physics")
        if not isinstance(physics_evidence, dict):
            raise ValueError("Scenario physics evidence is missing")
        if (
            physics_evidence.get("status") not in ("FAIL", "INCONCLUSIVE")
            or physics_evidence["status"] != self.physics_status
        ):
            raise ValueError(
                "Scenario physics status contradicts the actual assessment evidence"
            )
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
        # A Pydantic model_validator raises with loc=(). Such a root-level
        # contract error must be reported as a ValueError, never trigger an
        # IndexError that kills the job supervisor thread.
        fields = set()
        for error in exc.errors():
            loc = error.get("loc") or ()
            fields.add(str(loc[0]) if loc else "result")
        raise ValueError(
            f"Invalid {mode} result fields: {', '.join(sorted(fields))}"
        ) from exc

    if mode in ("convert", "scenario"):
        artifacts = result["artifacts"]
        for name, artifact in artifacts.items():
            filename = ARTIFACTS.get(name)
            if filename is None or artifact["filename"] != filename:
                raise ValueError(f"Invalid {mode} artifact descriptor: {name!r}")

    # Extension fields are allowed for non-scientific metadata only.
    # Enforce a single vocabulary for scientific verdicts across ALL modes:
    # e.g. a valid conversion result cannot add an unsanctioned
    # {"verdict": "SIMULATION_VERIFIED"} alongside its true status.
    claim_fields = {
        "status", "verdict", "verification", "mapping_status",
        "simulation_status", "output_complete", "mapping_acceptance",
        "simulation_acceptance", "acceptance_status", "verified",
        "is_verified", "scientific_acceptance",
    }
    allowed_claims = {
        "convert": {"status", "mapping_status", "simulation_status", "output_complete"},
        "scenario": {"status", "verdict", "simulation_status"},
        "preview": {"status", "verification"},
        "inventory": set(),
    }
    forbidden = (claim_fields - allowed_claims[mode]).intersection(result)
    if forbidden:
        descriptions = {
            "convert": "Conversion cannot declare extra scientific acceptance fields",
            "scenario": "Scenario cannot declare extra scientific acceptance fields",
            "preview": "Preview cannot declare scientific acceptance fields",
            "inventory": "Inventory cannot declare acceptance or downloadable artifacts",
        }
        raise ValueError(descriptions[mode] + ": " + ", ".join(sorted(forbidden)))
    if mode == "inventory" and "artifacts" in result:
        raise ValueError("Inventory cannot declare acceptance or downloadable artifacts")

    return result
