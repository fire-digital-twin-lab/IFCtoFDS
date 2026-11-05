"""Negative scientific acceptance tests: incomplete evidence must never promote a verdict.

These tests distinguish mapping equivalence, scenario plausibility, and actual
independent CFD verification. A passing setup/mesh check is not a CFD verdict.
"""

import pytest

from ifc_to_fds.adapters.jobs.result_contract import validate_job_result
from ifc_to_fds.domain.validation.model import (
    AcceptanceReport,
    GateResult,
    REQUIRED_MAPPING_GATES,
)
from ifc_to_fds.core.canonical import SCHEMA_VERSION


def valid_convert():
    """Minimal structurally valid, independently reported mapping result."""
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "MAPPING_VERIFIED",
        "mapping_status": "MAPPING_VERIFIED",
        "simulation_status": "INCONCLUSIVE",
        "output_complete": True,
        "source_filename": "fixture.ifc",
        "profile": "mapping",
        "coverage": {},
        "timings": {},
        "gates": {
            name: {
                "status": "PASS", "required": True,
                "reason": "Independently checked: " + name,
            }
            for name in REQUIRED_MAPPING_GATES
        },
        "findings": [],
        "findings_count": 0,
        "blocker_count": 0,
        "research": {},
        "artifacts": {
            "fds": {"filename": "model.fds"},
            "manifest": {"filename": "model_manifest.json"},
            "report": {"filename": "model_acceptance_report.json"},
            "geometry": {"filename": "model_geometry.json"},
        },
    }


def valid_scenario():
    return {
        "status": "COMPLETED",
        "verdict": "INCONCLUSIVE",
        "verdict_reason": "Independent CFD verification has not been performed",
        "mesh_status": "PASS",
        "physics_status": "INCONCLUSIVE",
        "simulation_status": "NOT_RUN",
        "peak_hrr_mw": 4.5,
        "evidence": {
            "fds_sha256": "a" * 64,
            "physics": {"status": "INCONCLUSIVE"},
        },
        "artifacts": {"scenario_fds": {"filename": "scenario.fds"}},
        "scenario_id": "ev-1",
        "bundle_sha256": "b" * 64,
        "fds_file": "scenario.fds",
    }


def complete_mapping_gates():
    return {
        name: GateResult(
            status="PASS",
            required=True,
            reason="Independent check completed",
        )
        for name in REQUIRED_MAPPING_GATES
    }


def test_mapping_aggregate_requires_full_independent_gate_set():
    report = AcceptanceReport(
        gates={"syntax": GateResult(status="PASS", required=True)}
    ).finalize()
    assert report.mapping_status == "INCONCLUSIVE"
    assert report.status == "INCONCLUSIVE"
    assert report.simulation_status == "INCONCLUSIVE"

    complete = AcceptanceReport(gates=complete_mapping_gates()).finalize()
    assert complete.mapping_status == "MAPPING_VERIFIED"
    assert complete.simulation_status == "INCONCLUSIVE"


@pytest.mark.parametrize("removed", sorted(REQUIRED_MAPPING_GATES))
def test_mapping_missing_any_mandatory_gate_is_inconclusive(removed):
    gates = complete_mapping_gates()
    del gates[removed]
    report = AcceptanceReport(gates=gates).finalize()
    assert report.mapping_status == "INCONCLUSIVE"


@pytest.mark.parametrize("name", sorted(REQUIRED_MAPPING_GATES))
def test_mapping_cannot_promote_optional_or_not_run_mandatory_gate(name):
    for replacement in (
        GateResult(status="PASS", required=False),
        GateResult(status="NOT_RUN", required=True),
        GateResult(status="NOT_APPLICABLE", required=True, reason=" "),
    ):
        gates = complete_mapping_gates()
        gates[name] = replacement
        report = AcceptanceReport(gates=gates).finalize()
        assert report.mapping_status == "INCONCLUSIVE"


@pytest.mark.parametrize("name", sorted(REQUIRED_MAPPING_GATES))
def test_persisted_verified_conversion_cannot_omit_mandatory_gate(name):
    result = valid_convert()
    result["gates"].pop(name)
    result["blocker_count"] = 0
    with pytest.raises(ValueError, match="Invalid convert result fields"):
        validate_job_result("convert", result)


def test_persisted_verified_conversion_cannot_mark_mandatory_gate_optional():
    result = valid_convert()
    result["gates"]["source_inventory"]["required"] = False
    result["blocker_count"] = 0
    with pytest.raises(ValueError, match="Invalid convert result fields"):
        validate_job_result("convert", result)


def test_simulation_profile_must_not_echo_mapping_verified_as_overall_verdict():
    result = valid_convert()
    result["profile"] = "simulation"
    # The mapping is verified, but no independent CFD scientific verification
    # has been executed: the overall simulation verdict cannot be verified.
    with pytest.raises(ValueError, match="Invalid convert result fields"):
        validate_job_result("convert", result)

    result["status"] = "INCONCLUSIVE"
    assert validate_job_result("convert", result) is result
    assert result["output_complete"] is True  # Mapping artifact, not CFD.


def test_mapping_profile_must_not_pretend_rejected_simulation_is_mapping_failure():
    result = valid_convert()
    result["simulation_status"] = "REJECTED"
    result["status"] = "REJECTED"
    with pytest.raises(ValueError, match="Invalid convert result fields"):
        validate_job_result("convert", result)


@pytest.mark.parametrize(
    "reported,evidence,verdict",
    [
        ("PASS", "INCONCLUSIVE", "INCONCLUSIVE"),
        ("INCONCLUSIVE", "FAIL", "INCONCLUSIVE"),
        ("FAIL", "INCONCLUSIVE", "FAIL"),
        ("INCONCLUSIVE", "PASS", "INCONCLUSIVE"),
    ],
)
def test_scenario_physics_status_must_agree_with_actual_assessment(
    reported, evidence, verdict
):
    result = valid_scenario()
    result["physics_status"] = reported
    result["evidence"]["physics"]["status"] = evidence
    result["verdict"] = verdict
    with pytest.raises(ValueError, match="Invalid scenario result fields"):
        validate_job_result("scenario", result)


def test_legitimate_scenario_energy_failure_still_rejected():
    result = valid_scenario()
    result["physics_status"] = "FAIL"
    result["evidence"]["physics"]["status"] = "FAIL"
    result["verdict"] = "FAIL"
    assert validate_job_result("scenario", result) is result
    assert result["simulation_status"] == "NOT_RUN"


def test_mapping_pass_does_not_promote_simulation_even_if_all_simulation_gates_pass():
    gates = complete_mapping_gates()
    for name in (
        "solver", "effective_geometry", "physics", "scenario",
        "mesh_resolution", "operational_model",
    ):
        gates[name] = GateResult(status="PASS")
    report = AcceptanceReport(
        requested_level="simulation", gates=gates
    ).finalize()
    assert report.mapping_status == "MAPPING_VERIFIED"
    assert report.simulation_status == report.status == "INCONCLUSIVE"
