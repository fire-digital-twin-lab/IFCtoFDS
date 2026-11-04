"""R10-05: an EV job is not simulation acceptance without an independent CFD audit."""

import inspect

import pytest

from ifc_to_fds.fire.scenario_verdict import (
    scenario_verdict,
    scenario_verdict_reason,
)


@pytest.mark.parametrize(
    ("mesh", "physics", "expected"),
    [
        ("PASS", "INCONCLUSIVE", "INCONCLUSIVE"),
        ("PASS", "PASS", "INCONCLUSIVE"),
        ("INCONCLUSIVE", "PASS", "INCONCLUSIVE"),
        ("NOT_RUN", "INCONCLUSIVE", "INCONCLUSIVE"),
        ("FAIL", "PASS", "FAIL"),
        ("PASS", "FAIL", "FAIL"),
        ("FAIL", "FAIL", "FAIL"),
        ("REJECTED", "INCONCLUSIVE", "FAIL"),
        ("PASS", "REJECTED", "FAIL"),
    ],
)
def test_ev_scenario_aggregate_cannot_promote_single_gate(mesh, physics, expected):
    assert scenario_verdict(mesh, physics) == expected


def test_reason_never_claims_simulation_verification():
    text = scenario_verdict_reason("PASS", "PASS")
    assert "not been verified" in text
    assert "simulation" in text.lower()


def test_worker_uses_shared_fail_closed_contract():
    from ifc_to_fds.adapters.jobs.runner import WorkerRunner

    source = inspect.getsource(WorkerRunner.execute)
    assert "scenario_verdict(mesh_status, physics_status)" in source
    assert '"simulation_status": "NOT_RUN"' in source
    assert '"verdict": verdict' in source
    assert '"verdict_reason": scenario_verdict_reason' in source


def test_energy_budget_sufficiency_does_not_mean_cfd_acceptance():
    # Even an independently sourced, sufficient nominal energy budget and
    # a mesh resolution PASS do not prove field measurements or solver output.
    assert scenario_verdict("PASS", "INCONCLUSIVE") == "INCONCLUSIVE"
    assert scenario_verdict("PASS", "PASS") == "INCONCLUSIVE"
