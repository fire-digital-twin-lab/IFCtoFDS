"""Fail-closed status contract for EV scenario jobs.

A syntax/mesh check succeeding is not physical or simulation verification.
The EV workflow currently does not produce SIMULATION_VERIFIED evidence.
"""

from typing import Literal


ScenarioVerdict = Literal["FAIL", "INCONCLUSIVE"]


def scenario_verdict(mesh_status: str, physics_status: str) -> ScenarioVerdict:
    """Aggregate distinct gate results without treating a stage PASS as acceptance.

    FAIL is supported by either a failed mesh or physics plausibility check.
    Otherwise, the scenario remains INCONCLUSIVE, even when mesh_status is PASS,
    because no independent CFD/simulation verification has been established.
    """
    if mesh_status in ("FAIL", "REJECTED") or physics_status in ("FAIL", "REJECTED"):
        return "FAIL"
    return "INCONCLUSIVE"


def scenario_verdict_reason(mesh_status: str, physics_status: str) -> str:
    if mesh_status in ("FAIL", "REJECTED"):
        return "Mesh resolution check failed; scenario cannot be accepted"
    if physics_status in ("FAIL", "REJECTED"):
        return "Declared energy budget / physics plausibility check failed"
    return (
        "Scenario generated but independent CFD simulation has not been "
        "verified; mesh or energy checks alone cannot establish acceptance"
    )
