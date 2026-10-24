"""Tests for fire mesh resolution gate (Task 4)."""

import pytest

from ifc_to_fds.domain.validation.model import (
    AuditConfig,
    GateStatus,
    ValidationContext,
)
from ifc_to_fds.fire import (
    EVSelection,
    ScenarioBundle,
    calculate_d_star,
    check_mesh_resolution,
    emit_fire_scenario,
)
from ifc_to_fds.validation.checkers.mesh_resolution import MeshResolutionChecker
from ifc_to_fds.validation.runner import ValidationRunner


def test_mesh_gate_blocks_coarse_cell():
    """Verify check_mesh_resolution blocks coarse cell size when D*/dx < 4.0."""
    # 5MW nominal fire: D* = (5000 / 1111.4)^0.4 ~= 1.821m.
    # At cell_size = 0.5m, D*/dx = 1.821 / 0.5 = 3.64 < 4.0.
    scenario_7mw = {"total_peak_hrr_mw": 5.0}
    res = check_mesh_resolution(scenario_7mw, cell_size=0.5)
    assert res.status != GateStatus.PASS
    assert res.status == GateStatus.FAIL
    assert "Mesh resolution too coarse" in res.reason
    assert res.evidence["d_star_over_dx"] < 4.0


def test_mesh_gate_passes_appropriate_resolution():
    """Verify 5MW fire with cell_size=0.2 passes (D*/dx ~= 9.1 in [4, 16])."""
    scenario_5mw = {"total_peak_hrr_mw": 5.0}
    res = check_mesh_resolution(scenario_5mw, cell_size=0.2)
    assert res.status == GateStatus.PASS
    assert res.evidence["d_star_over_dx"] == pytest.approx(9.1065, rel=1e-2)
    assert "Mesh resolution adequate" in res.reason


def test_mesh_gate_blocks_coarse_ebike():
    """Verify 100 kW e-bike with cell_size=0.2 fails (D*/dx ~= 1.9 < 4)."""
    scenario_ebike = {"peak_hrr_kw": 100.0}
    res = check_mesh_resolution(scenario_ebike, cell_size=0.2)
    assert res.status == GateStatus.FAIL
    assert res.evidence["d_star_over_dx"] == pytest.approx(1.9045, rel=1e-2)
    assert "Mesh resolution too coarse" in res.reason


def test_mesh_gate_passes_very_fine_mesh():
    """Verify D*/dx > 16.0 passes with very fine resolution note."""
    scenario_5mw = {"total_peak_hrr_mw": 5.0}
    res = check_mesh_resolution(scenario_5mw, cell_size=0.05)
    assert res.status == GateStatus.PASS
    assert res.evidence["d_star_over_dx"] > 16.0
    assert "very fine" in res.reason


def test_mesh_resolution_checker_not_applicable_when_no_fire(box_model):
    """Verify non-fire FDS yields NOT_APPLICABLE status."""
    fds_text = (
        "&HEAD CHID='NO_FIRE', TITLE='No fire simulation' /\n"
        "&TIME T_END=10.0 /\n"
        "&MESH ID='M1', IJK=10,10,10, XB=0.0,2.0,0.0,1.0,0.0,3.0 /\n"
        "&SURF ID='WALL', COLOR='GRAY' /\n"
        "&OBST XB=0.0,2.0,0.0,1.0,0.0,0.2, SURF_ID='WALL' /\n"
        "&TAIL /\n"
    )
    runner = ValidationRunner()
    context = runner.create_context(box_model, fds_text)
    checker = MeshResolutionChecker()
    outcome = checker.check(context)

    assert outcome.result.status == GateStatus.NOT_APPLICABLE
    assert "No fire sources defined for mesh resolution checking" in outcome.result.reason


def test_mesh_resolution_checker_with_scenario_fds(box_model):
    """Verify FDS containing scenario fragment executes mesh_resolution gate cleanly."""
    plan = getattr(box_model, "mapping_plan", None)
    if plan is None:
        from ifc_to_fds.domain.mapping import MappingPlan
        plan = MappingPlan()

    ev = EVSelection(preset_id="auto-nmc", position=(1.0, 0.5, 0.5))
    bundle = emit_fire_scenario(
        mapping_plan=plan,
        bundle_sha256="b" * 64,
        ev_selections=[ev],
        verification_status="MAPPING_VERIFIED",
    )

    fds_text = (
        "&HEAD CHID='EV_FIRE', TITLE='EV Fire Simulation' /\n"
        "&TIME T_END=60.0 /\n"
        "&MESH ID='M1', IJK=10,10,10, XB=0.0,2.0,0.0,2.0,0.0,2.0 /\n"
        f"{bundle.fds_fragment}\n"
        "&TAIL /\n"
    )

    runner = ValidationRunner()
    report = runner.validate(box_model, fds_text)

    assert "mesh_resolution" in report.gates
    mesh_gate = report.gates["mesh_resolution"]
    assert mesh_gate.status == GateStatus.PASS
    assert mesh_gate.evidence["cell_size_m"] == pytest.approx(0.2, rel=1e-3)
    assert 4.0 <= mesh_gate.evidence["d_star_over_dx"] <= 16.0


def test_calculate_d_star_values():
    """Verify D* calculation values and boundary behavior."""
    assert calculate_d_star(0.0) == 0.0
    assert calculate_d_star(-50.0) == 0.0
    # 5000 kW: (5000 / 1111.4)^0.4 ~= 1.8249
    assert calculate_d_star(5000.0) == pytest.approx(1.8249, rel=1e-3)
    # 100 kW: (100 / 1111.4)^0.4 ~= 0.3817
    assert calculate_d_star(100.0) == pytest.approx(0.3817, rel=1e-3)


def test_check_mesh_resolution_with_scenario_bundle():
    """Verify ScenarioBundle object is directly consumable by check_mesh_resolution."""
    bundle = ScenarioBundle(
        scenario_id="ev_scen_test",
        bundle_sha256="c" * 64,
        ev_library_version="1.0.0",
        fds_fragment="! test",
        total_peak_hrr_mw=4.5,
        ev_count=1,
    )
    res = check_mesh_resolution(bundle, cell_size=0.2)
    assert res.status == GateStatus.PASS
    # 4.5 MW = 4500 kW -> D* = (4500/1111.4)^0.4 ~= 1.7454 -> D*/0.2 ~= 8.727
    assert res.evidence["peak_hrr_kw"] == 4500.0
    assert res.evidence["d_star_over_dx"] == pytest.approx(8.727, rel=1e-2)
