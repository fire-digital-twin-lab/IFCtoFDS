"""P4c2b application-study readiness regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ifc_to_fds.fire.grid_sensitivity_application import (
    assess_application_grid_study_readiness,
    require_application_grid_study_ready,
)


def _ready_values():
    domain = {
        "xmin": 0.0,
        "xmax": 20.0,
        "ymin": 0.0,
        "ymax": 12.0,
        "zmin": 0.0,
        "zmax": 4.0,
    }
    return {
        "acceptance-profile.json": {
            "schema_version": "0.5.0",
            "configuration": {
                "profile": "research-basement",
                "simulation_domain": domain,
            },
        },
        "scope.json": {
            "scope": {"storeys": ["B1"]},
            "simulation_domain": domain,
        },
        "golden-manifest.json": {
            "schema_version": "0.5.0",
            "simulation_domain": domain,
            "mapping_acceptance": "MAPPING_VERIFIED",
            "output_complete": True,
            "geometry_package_sha256": "a" * 64,
        },
        "geometry-package.json": {"sha256": "a" * 64},
        "sources.json": {
            "sources": [
                {
                    "source_id": "b" * 64,
                    "file_hash_sha256": "b" * 64,
                }
            ]
        },
    }


def test_tracked_basement_reference_is_not_ready_for_p4c2b():
    readiness = assess_application_grid_study_readiness(
        "reference-cases/basement-b1-b2"
    )

    assert readiness.status == "NOT_READY"
    assert readiness.approval_status == "DRAFT"
    assert readiness.reference_schema_version == "0.4.0"
    assert readiness.simulation_domain is None
    assert readiness.mapping_acceptance == "INCONCLUSIVE"
    assert readiness.output_complete is False
    assert readiness.sources_verified is False
    assert set(readiness.blockers) >= {
        "REFERENCE_NOT_HUMAN_APPROVED",
        "REFERENCE_SCHEMA_NOT_CURRENT",
        "GOLDEN_MANIFEST_SCHEMA_NOT_CURRENT",
        "SIMULATION_DOMAIN_NOT_APPROVED",
        "REFERENCE_MAPPING_NOT_VERIFIED",
        "REFERENCE_OUTPUT_INCOMPLETE",
        "REFERENCE_GEOMETRY_PACKAGE_NOT_BOUND",
        "EXTERNAL_SOURCES_NOT_RESOLVED",
    }


def test_readiness_requires_all_reference_and_source_preconditions(monkeypatch):
    approval = {
        "status": "APPROVED",
        "reviewer": "independent-reviewer",
        "rationale": "Reviewed application baseline",
        "evidence": ["review-record"],
    }
    values = _ready_values()

    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_application.inspect_case",
        lambda case: ("c" * 64, approval, values),
    )
    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_application.resolve_sources",
        lambda case, mapping: [Path("/external/approved.ifc")],
    )

    readiness = assess_application_grid_study_readiness(
        "reference-cases/application-approved",
        {"b" * 64: "/external/approved.ifc"},
    )

    assert readiness.status == "READY"
    assert readiness.blockers == []
    assert readiness.reference_sha256 == "c" * 64
    assert readiness.sources_verified is True
    assert readiness.mapping_acceptance == "MAPPING_VERIFIED"
    assert readiness.output_complete is True
    require_application_grid_study_ready(readiness)


def test_readiness_rejects_geometry_package_digest_mismatch(monkeypatch):
    approval = {
        "status": "APPROVED",
        "reviewer": "reviewer",
        "rationale": "Reviewed",
        "evidence": ["evidence"],
    }
    values = _ready_values()
    values["geometry-package.json"]["sha256"] = "f" * 64

    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_application.inspect_case",
        lambda case: ("e" * 64, approval, values),
    )
    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_application.resolve_sources",
        lambda case, mapping: [Path("/external/approved.ifc")],
    )

    readiness = assess_application_grid_study_readiness(
        "reference-cases/application-package-mismatch",
        {"b" * 64: "/external/approved.ifc"},
    )

    assert readiness.status == "NOT_READY"
    assert "REFERENCE_GEOMETRY_PACKAGE_DIGEST_MISMATCH" in readiness.blockers


def test_readiness_rejects_domain_drift_and_source_integrity_failure(monkeypatch):
    approval = {
        "status": "APPROVED",
        "reviewer": "reviewer",
        "rationale": "Reviewed",
        "evidence": ["evidence"],
    }
    values = _ready_values()
    values["golden-manifest.json"]["simulation_domain"] = {
        **values["golden-manifest.json"]["simulation_domain"],
        "xmax": 21.0,
    }

    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_application.inspect_case",
        lambda case: ("d" * 64, approval, values),
    )

    def fail_sources(case, mapping):
        raise ValueError("External fixture checksum mismatch")

    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_application.resolve_sources",
        fail_sources,
    )

    readiness = assess_application_grid_study_readiness(
        "reference-cases/application-drift",
        {"b" * 64: "/external/changed.ifc"},
    )

    assert readiness.status == "NOT_READY"
    assert "GOLDEN_MANIFEST_DOMAIN_MISMATCH" in readiness.blockers
    assert "EXTERNAL_SOURCE_INTEGRITY_FAILED" in readiness.blockers
    with pytest.raises(ValueError, match="P4c2b application grid study is not ready"):
        require_application_grid_study_ready(readiness)


def test_readiness_fails_closed_on_reference_integrity_error(monkeypatch):
    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_application.inspect_case",
        lambda case: (_ for _ in ()).throw(
            ValueError("Reference bundle changed after its recorded revision")
        ),
    )

    readiness = assess_application_grid_study_readiness("broken-reference")

    assert readiness.status == "NOT_READY"
    assert readiness.blockers == ["REFERENCE_INTEGRITY_INVALID"]
    with pytest.raises(ValueError):
        require_application_grid_study_ready(readiness)
