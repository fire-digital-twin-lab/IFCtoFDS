"""Fail-closed readiness gate for application-relevant P4c2b grid studies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.domain.version import SCHEMA_VERSION
from ifc_to_fds.validation.golden import inspect_case, resolve_sources

from .grid_sensitivity_application_models import ApplicationGridStudyReadiness


def _domain(payload: Any) -> dict[str, float] | None:
    if not isinstance(payload, dict):
        return None
    try:
        box = BoundingBox.model_validate(payload)
    except (TypeError, ValueError):
        return None
    if not (
        box.xmax > box.xmin
        and box.ymax > box.ymin
        and box.zmax > box.zmin
    ):
        return None
    return {
        "xmin": box.xmin,
        "xmax": box.xmax,
        "ymin": box.ymin,
        "ymax": box.ymax,
        "zmin": box.zmin,
        "zmax": box.zmax,
    }


def assess_application_grid_study_readiness(
    reference_case: str | Path,
    source_map: dict[str, str] | None = None,
) -> ApplicationGridStudyReadiness:
    """Assess whether a reviewed reference is eligible for P4c2b execution.

    This function never approves a reference. It only verifies the immutable
    bundle, existing human approval metadata, current schema/domain/mapping
    evidence, and externally supplied source-file checksums.
    """

    case_path = Path(reference_case)
    blockers: list[str] = []
    checksum: str | None = None
    approval: dict[str, Any] = {}
    values: dict[str, Any] = {}

    try:
        checksum, approval, values = inspect_case(case_path)
    except FileNotFoundError:
        blockers.append("REFERENCE_FILES_UNAVAILABLE")
    except (OSError, ValueError, TypeError, KeyError):
        blockers.append("REFERENCE_INTEGRITY_INVALID")

    if not values:
        return ApplicationGridStudyReadiness(
            status="NOT_READY",
            reason="Reference bundle is unavailable or failed integrity validation.",
            reference_case=case_path.name or str(case_path),
            reference_sha256=checksum,
            approval_status=approval.get("status"),
            reviewer=approval.get("reviewer"),
            current_schema_version=SCHEMA_VERSION,
            blockers=blockers,
        )

    approved = approval.get("status") == "APPROVED" and all(
        approval.get(key) for key in ("reviewer", "rationale", "evidence")
    )
    if not approved:
        blockers.append("REFERENCE_NOT_HUMAN_APPROVED")

    profile = values.get("acceptance-profile.json", {})
    schema_version = profile.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        blockers.append("REFERENCE_SCHEMA_NOT_CURRENT")

    scope_payload = values.get("scope.json", {})
    simulation_domain = _domain(scope_payload.get("simulation_domain"))
    if simulation_domain is None:
        blockers.append("SIMULATION_DOMAIN_NOT_APPROVED")

    profile_configuration = profile.get("configuration", {})
    profile_domain = _domain(profile_configuration.get("simulation_domain"))
    if simulation_domain is not None and profile_domain != simulation_domain:
        blockers.append("REFERENCE_DOMAIN_METADATA_MISMATCH")

    manifest = values.get("golden-manifest.json", {})
    if manifest.get("schema_version") != SCHEMA_VERSION:
        blockers.append("GOLDEN_MANIFEST_SCHEMA_NOT_CURRENT")
    manifest_domain = _domain(manifest.get("simulation_domain"))
    if simulation_domain is not None and manifest_domain != simulation_domain:
        blockers.append("GOLDEN_MANIFEST_DOMAIN_MISMATCH")

    mapping_acceptance = manifest.get("mapping_acceptance")
    if mapping_acceptance != "MAPPING_VERIFIED":
        blockers.append("REFERENCE_MAPPING_NOT_VERIFIED")

    output_complete = manifest.get("output_complete")
    if output_complete is not True:
        blockers.append("REFERENCE_OUTPUT_INCOMPLETE")

    geometry_digest = manifest.get("geometry_package_sha256")
    if (
        not isinstance(geometry_digest, str)
        or len(geometry_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in geometry_digest)
    ):
        blockers.append("REFERENCE_GEOMETRY_PACKAGE_NOT_BOUND")
    else:
        geometry_package = values.get("geometry-package.json", {})
        package_digest = (
            geometry_package.get("sha256")
            if hasattr(geometry_package, "get")
            else None
        )
        if package_digest != geometry_digest:
            blockers.append("REFERENCE_GEOMETRY_PACKAGE_DIGEST_MISMATCH")

    sources = values.get("sources.json", {}).get("sources", [])
    source_count = len(sources) if isinstance(sources, list) else 0
    if source_count < 1:
        blockers.append("REFERENCE_SOURCES_EMPTY")
    sources_verified = False
    if source_map is None:
        blockers.append("EXTERNAL_SOURCES_NOT_RESOLVED")
    else:
        try:
            resolved = resolve_sources(case_path, source_map)
            sources_verified = len(resolved) == source_count and source_count > 0
            if not sources_verified:
                blockers.append("EXTERNAL_SOURCE_SET_INCOMPLETE")
        except (OSError, ValueError, TypeError, KeyError):
            blockers.append("EXTERNAL_SOURCE_INTEGRITY_FAILED")

    blockers = list(dict.fromkeys(blockers))
    ready = not blockers
    return ApplicationGridStudyReadiness(
        status="READY" if ready else "NOT_READY",
        reason=(
            "Reference bundle, human approval, current schema/domain, verified mapping "
            "output and external source checksums satisfy the P4c2b execution preconditions."
            if ready
            else "Application grid study execution is blocked by unresolved reference, "
            "mapping, domain or external-source prerequisites."
        ),
        reference_case=case_path.name or str(case_path),
        reference_sha256=checksum,
        approval_status=approval.get("status"),
        reviewer=approval.get("reviewer"),
        reference_schema_version=schema_version,
        current_schema_version=SCHEMA_VERSION,
        simulation_domain=simulation_domain,
        source_count=source_count,
        sources_verified=sources_verified,
        mapping_acceptance=mapping_acceptance,
        output_complete=output_complete if isinstance(output_complete, bool) else None,
        blockers=blockers,
    )


def require_application_grid_study_ready(
    readiness: ApplicationGridStudyReadiness,
) -> None:
    """Block P4c2b execution until all application-reference prerequisites hold."""

    if not readiness.ready:
        raise ValueError(
            "P4c2b application grid study is not ready: "
            + ", ".join(readiness.blockers)
        )
