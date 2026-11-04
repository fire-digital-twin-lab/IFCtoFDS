"""R10-04 safety tests: validator comparison never grants verification."""

import pytest

from ifc_to_fds.domain.validation.model import (
    AcceptanceReport, GateResult, GateStatus,
)
from ifc_to_fds.validation.parity_contract import compare_validation_reports


def _report():
    report = AcceptanceReport(
        status="INCONCLUSIVE", mapping_status="INCONCLUSIVE",
        simulation_status="INCONCLUSIVE", total_elements_checked=1,
        element_statuses={"fixture:1": "MATCHED"},
        matched_count=1,
        gates={
            "geometry": GateResult(status=GateStatus.PASS, reason="Verified full solid"),
            "source_inventory": GateResult(
                status=GateStatus.INCONCLUSIVE, reason="Source not independently re-read"
            ),
            "solver": GateResult(status=GateStatus.NOT_RUN, required=False),
        },
        metrics={"solid_iou": 1.0, "solver_s": 0.5},
    )
    return report


def test_identical_report_has_no_differences():
    report = _report()
    parity = compare_validation_reports(report, report.model_copy(deep=True), compare_details=True)
    assert parity.equivalent
    parity.assert_equivalent()


@pytest.mark.parametrize(
    "mutation,expected_path",
    [
        ("downgrade_gate", "gates.geometry.status"),
        ("promote_unverified", "status"),
        ("omit_gate", "gates.source_inventory"),
        ("omit_entity", "element_statuses.fixture:1"),
        ("change_count", "matched_count"),
        ("change_required", "gates.solver.required"),
    ],
)
def test_parity_fails_closed_on_mismatches(mutation, expected_path):
    authoritative = _report()
    candidate = authoritative.model_copy(deep=True)
    if mutation == "downgrade_gate":
        candidate.gates["geometry"].status = GateStatus.FAIL
    elif mutation == "promote_unverified":
        candidate.status = "MAPPING_VERIFIED"
    elif mutation == "omit_gate":
        del candidate.gates["source_inventory"]
    elif mutation == "omit_entity":
        candidate.element_statuses.clear()
    elif mutation == "change_count":
        candidate.matched_count = 0
    else:
        candidate.gates["solver"].required = True
    verdict = compare_validation_reports(authoritative, candidate)
    assert not verdict.equivalent
    assert any(d.path == expected_path for d in verdict.differences)
    with pytest.raises(AssertionError, match="not semantically equivalent"):
        verdict.assert_equivalent()
    assert authoritative.status.value == "INCONCLUSIVE"


def test_detailed_mode_catches_evidence_reason_and_metric_mutations():
    original = _report()
    candidate = original.model_copy(deep=True)
    candidate.gates["geometry"].evidence["source_sha256"] = "tampered"
    candidate.gates["geometry"].reason = "Accepted without evidence"
    candidate.metrics["solid_iou"] = 0.5
    candidate.metrics["solver_s"] = 99.0

    basic = compare_validation_reports(original, candidate)
    assert basic.equivalent  # explains why stage 1 parity alone is inadequate
    strict = compare_validation_reports(original, candidate, compare_details=True)
    assert not strict.equivalent
    paths = {difference.path for difference in strict.differences}
    assert "gates.geometry.evidence.source_sha256" in paths
    assert "gates.geometry.reason" in paths
    assert "metrics.solid_iou" in paths
    assert "metrics.solver_s" not in paths  # performance, not scientific content


def test_extra_runner_gate_is_not_silently_accepted():
    authoritative = _report()
    candidate = authoritative.model_copy(deep=True)
    candidate.gates["effective_geometry"] = GateResult(
        status=GateStatus.PASS, required=False, reason="not independently proven"
    )
    diff = compare_validation_reports(authoritative, candidate)
    assert any(d.path == "gates.effective_geometry" for d in diff.differences)
