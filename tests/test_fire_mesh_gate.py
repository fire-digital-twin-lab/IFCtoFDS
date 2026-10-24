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
    """Verify D*/dx > 16.0 does NOT pass (strictly enforce 4.0 <= D*/dx <= 16.0)."""
    scenario_5mw = {"total_peak_hrr_mw": 5.0}
    res = check_mesh_resolution(scenario_5mw, cell_size=0.05)
    assert res.status != GateStatus.PASS
    assert res.status == GateStatus.FAIL
    assert res.evidence["d_star_over_dx"] > 16.0
    assert "Mesh resolution too fine" in res.reason
    assert "exceeds validated [4.0, 16.0] range" in res.reason


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


def test_solver_blocked_when_mesh_resolution_fails(box_model, monkeypatch):
    """When mesh resolution fails, runner sets solver gate to INCONCLUSIVE without calling solver."""
    solver_called = False

    def fake_solver_gates(fds_text, config):
        nonlocal solver_called
        solver_called = True
        return GateResult(status=GateStatus.PASS), GateResult(status=GateStatus.PASS)

    monkeypatch.setattr("ifc_to_fds.validation.checkers.solver.solver_gates", fake_solver_gates)

    plan = getattr(box_model, "mapping_plan", None)
    if plan is None:
        from ifc_to_fds.domain.mapping import MappingPlan
        plan = MappingPlan()

    # e-bike-lfp produces ~100 kW -> D* ~ 0.38m -> cell_size 0.5m yields D*/dx ~ 0.76 < 4.0 (fails)
    ev = EVSelection(preset_id="e-bike-lfp", position=(1.0, 0.5, 0.5))
    bundle = emit_fire_scenario(
        mapping_plan=plan,
        bundle_sha256="b" * 64,
        ev_selections=[ev],
        verification_status="MAPPING_VERIFIED",
    )

    fds_text = (
        "&HEAD CHID='EV_FIRE_COARSE', TITLE='EV Fire Coarse Mesh' /\n"
        "&TIME T_END=60.0 /\n"
        "&MESH ID='M1', IJK=4,4,4, XB=0.0,2.0,0.0,2.0,0.0,2.0 /\n"
        f"{bundle.fds_fragment}\n"
        "&TAIL /\n"
    )

    runner = ValidationRunner()
    report = runner.validate(box_model, fds_text)

    assert report.gates["mesh_resolution"].status == GateStatus.FAIL
    assert report.gates["solver"].status == GateStatus.INCONCLUSIVE
    assert "Mesh resolution gate did not pass" in report.gates["solver"].reason
    assert not solver_called


def test_mesh_gate_multi_source_fails_if_any_source_out_of_bounds():
    """Verify check_mesh_resolution evaluates each vehicle selection individually."""
    ev_auto = EVSelection(preset_id="auto-nmc", position=(1.0, 0.5, 0.5))
    ev_ebike = EVSelection(preset_id="e-bike-lfp", position=(5.0, 0.5, 0.5))

    bundle = ScenarioBundle(
        scenario_id="ev_scen_multi",
        bundle_sha256="d" * 64,
        ev_library_version="1.0.0",
        fds_fragment="! multi",
        total_peak_hrr_mw=4.6,
        ev_count=2,
        ev_selections=[ev_auto, ev_ebike],
    )

    # cell_size 0.2m: auto-nmc (4.5MW) -> D*/dx ~ 8.7 (pass); e-bike-lfp (0.1MW) -> D*/dx ~ 1.9 (fail)
    res = check_mesh_resolution(bundle, cell_size=0.2)
    assert res.status == GateStatus.FAIL
    assert "e-bike-lfp" in res.reason
    assert "< 4.0" in res.reason


def test_mesh_resolution_checker_multi_burner_evaluates_per_source(box_model):
    """Verify MeshResolutionChecker evaluates each detected burner individually."""
    fds_text = (
        "&HEAD CHID='MULTI_BURNER', TITLE='Multi burner test' /\n"
        "&TIME T_END=60.0 /\n"
        "&MESH ID='M1', IJK=10,10,10, XB=0.0,2.0,0.0,2.0,0.0,2.0 /\n"
        "&REAC ID='REAC_TEST', FUEL='OFFGAS', C=2.0, H=4.0, O=1.0 /\n"
        "&SURF ID='BURNER_AUTO', HRRPUA=555.56 /\n"
        "&VENT ID='VENT_AUTO', XB=0.0,4.5,0.0,1.8,0.0,0.0, SURF_ID='BURNER_AUTO' /\n"
        "&SURF ID='BURNER_EBIKE', HRRPUA=92.59 /\n"
        "&VENT ID='VENT_EBIKE', XB=5.0,6.8,0.0,0.6,0.0,0.0, SURF_ID='BURNER_EBIKE' /\n"
        "&TAIL /\n"
    )
    runner = ValidationRunner()
    context = runner.create_context(box_model, fds_text)
    checker = MeshResolutionChecker()
    outcome = checker.check(context)

    assert outcome.result.status == GateStatus.FAIL
    assert "VENT_EBIKE" in outcome.result.reason or "BURNER_EBIKE" in outcome.result.reason
    assert "< 4.0" in outcome.result.reason


def test_mesh_resolution_checker_dimensional_fallback_inconclusive(box_model):
    """If burning area cannot be determined from geometry, return INCONCLUSIVE."""
    fds_text = (
        "&HEAD CHID='NO_AREA', TITLE='No area test' /\n"
        "&TIME T_END=60.0 /\n"
        "&MESH ID='M1', IJK=10,10,10, XB=0.0,2.0,0.0,2.0,0.0,2.0 /\n"
        "&REAC ID='REAC_TEST', FUEL='OFFGAS', C=2.0, H=4.0, O=1.0 /\n"
        "&SURF ID='FIRE_SURF', HRRPUA=500.0 /\n"
        "&TAIL /\n"
    )
    runner = ValidationRunner()
    context = runner.create_context(box_model, fds_text)
    checker = MeshResolutionChecker()
    outcome = checker.check(context)

    assert outcome.result.status == GateStatus.INCONCLUSIVE
    assert "Cannot determine burning area for HRR calculation" in outcome.result.reason

