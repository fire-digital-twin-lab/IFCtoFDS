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


def test_mesh_gate_reports_low_dstar_indicator_without_universal_fail():
    """D*/dx below 4 is evidence, not a universal scientific FAIL threshold."""
    # 5MW nominal fire: D* = (5000 / 1111.4)^0.4 ~= 1.821m.
    # At cell_size = 0.5m, D*/dx = 1.821 / 0.5 = 3.64 < 4.0.
    scenario_7mw = {"total_peak_hrr_mw": 5.0}
    res = check_mesh_resolution(scenario_7mw, cell_size=0.5)
    assert res.status == GateStatus.INCONCLUSIVE
    assert "indicator only" in res.reason
    assert res.evidence["d_star_over_dx"] < 4.0
    assert (
        res.evidence["source_evaluations"][0]["indicator_band"]
        == "BELOW_HISTORICAL_4_16_SUBSET"
    )
    assert res.evidence["grid_sensitivity_required"] is True


def test_mesh_gate_does_not_promote_historical_4_16_subset_to_pass():
    """A D*/dx value inside the historical subset remains indicator-only."""
    scenario_5mw = {"total_peak_hrr_mw": 5.0}
    res = check_mesh_resolution(scenario_5mw, cell_size=0.2)
    assert res.status == GateStatus.INCONCLUSIVE
    assert res.evidence["d_star_over_dx"] == pytest.approx(9.1065, rel=1e-2)
    assert (
        res.evidence["source_evaluations"][0]["indicator_band"]
        == "WITHIN_HISTORICAL_4_16_SUBSET"
    )
    assert res.evidence["historical_4_16_is_acceptance_rule"] is False


def test_mesh_gate_reports_low_ebike_indicator_as_inconclusive():
    """A low-resolution e-bike indicator cannot substitute for grid sensitivity."""
    scenario_ebike = {"peak_hrr_kw": 100.0}
    res = check_mesh_resolution(scenario_ebike, cell_size=0.2)
    assert res.status == GateStatus.INCONCLUSIVE
    assert res.evidence["d_star_over_dx"] == pytest.approx(1.9045, rel=1e-2)
    assert (
        res.evidence["source_evaluations"][0]["indicator_band"]
        == "BELOW_HISTORICAL_4_16_SUBSET"
    )


def test_mesh_gate_does_not_reject_fine_mesh_for_exceeding_16():
    """A fine mesh above historical D*/dx values is not automatically wrong."""
    scenario_5mw = {"total_peak_hrr_mw": 5.0}
    res = check_mesh_resolution(scenario_5mw, cell_size=0.05)
    assert res.status == GateStatus.INCONCLUSIVE
    assert res.evidence["d_star_over_dx"] > 16.0
    assert (
        res.evidence["source_evaluations"][0]["indicator_band"]
        == "ABOVE_HISTORICAL_4_16_SUBSET"
    )
    assert "too fine" not in res.reason.lower()
    assert res.evidence["historical_4_16_is_acceptance_rule"] is False


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
    assert mesh_gate.status == GateStatus.INCONCLUSIVE
    assert mesh_gate.evidence["cell_size_m"] == pytest.approx(0.2, rel=1e-3)
    assert mesh_gate.evidence["grid_sensitivity_required"] is True


def test_mesh_gate_reports_critical_geometry_cells_without_thresholds():
    scenario = {
        "total_peak_hrr_mw": 5.0,
        "vehicle_geometries": [
            {
                "ground_clearance_m": 0.15,
                "battery_bounds": {
                    "xmin": 0.0,
                    "xmax": 4.0,
                    "ymin": 0.0,
                    "ymax": 1.5,
                    "zmin": 0.20,
                    "zmax": 0.35,
                },
            }
        ],
    }
    res = check_mesh_resolution(scenario, cell_size=0.05)

    assert res.status == GateStatus.INCONCLUSIVE
    metric = res.evidence["critical_geometry_resolution"][0]
    assert metric["ground_clearance_over_dx"] == pytest.approx(3.0)
    assert metric["battery_thickness_over_dx"] == pytest.approx(3.0)
    assert res.evidence["grid_sensitivity_required"] is True


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
    assert res.status == GateStatus.INCONCLUSIVE
    # 4.5 MW = 4500 kW -> D* = (4500/1111.4)^0.4 ~= 1.7454 -> D*/0.2 ~= 8.727
    assert res.evidence["peak_hrr_kw"] == 4500.0
    assert res.evidence["d_star_over_dx"] == pytest.approx(8.727, rel=1e-2)


def test_check_mesh_resolution_rejects_ambiguous_units():
    """H-1: verify ambiguous unit keys and bare scalars are rejected."""
    with pytest.raises(ValueError, match="Ambiguous key 'total_peak_hrr'"):
        check_mesh_resolution({"total_peak_hrr": 50.0}, cell_size=0.2)

    with pytest.raises(TypeError, match="Scalar number for scenario HRR is ambiguous"):
        check_mesh_resolution(50.0, cell_size=0.2)


def test_device_selection_sanitization_and_injection_defense():
    """H-7: verify DeviceSelection whitelists quantities and rejects injection."""
    from ifc_to_fds.fire.scenario_emitter import DeviceSelection

    # Valid device
    dev = DeviceSelection(
        id="DEV_TEMP_1",
        device_type="thermocouple",
        position=(1.0, 2.0, 1.5),
        setpoint=68.0,
        quantity="TEMPERATURE",
    )
    assert dev.quantity == "TEMPERATURE"

    # Injection attempt in quantity
    with pytest.raises(ValueError, match="disallowed characters|Invalid FDS device quantity"):
        DeviceSelection(
            id="D1",
            device_type="thermocouple",
            position=(1.0, 2.0, 1.5),
            setpoint=1.0,
            quantity="TEMPERATURE' /\n&OBST XB=0,1,0,1,0,1, SURF_ID='INERT",
        )

    # Disallowed quantity
    with pytest.raises(ValueError, match="Invalid FDS device quantity"):
        DeviceSelection(
            id="D1",
            device_type="sensor",
            position=(1.0, 1.0, 1.0),
            setpoint=0.0,
            quantity="NON_EXISTENT_QUANTITY",
        )



def test_solver_integration_runs_even_when_mesh_adequacy_is_inconclusive(
    box_model, monkeypatch
):
    """Solver evidence remains collectable while mesh adequacy stays separate."""
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

    # e-bike-lfp produces ~100 kW -> D* ~ 0.38m -> D*/dx ~ 0.76.
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

    assert report.gates["mesh_resolution"].status == GateStatus.INCONCLUSIVE
    assert report.gates["solver"].status == GateStatus.PASS
    assert report.gates["solver"].evidence["mesh_adequacy_status"] == "INCONCLUSIVE"
    assert solver_called


def test_mesh_gate_multi_source_reports_each_indicator_without_acceptance_band():
    """Each source keeps its own D*/dx indicator; none creates a universal threshold."""
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

    res = check_mesh_resolution(bundle, cell_size=0.2)
    assert res.status == GateStatus.INCONCLUSIVE
    by_vehicle = {e["vehicle"]: e for e in res.evidence["ev_evaluations"]}
    assert (
        by_vehicle["auto-nmc"]["indicator_band"]
        == "WITHIN_HISTORICAL_4_16_SUBSET"
    )
    assert (
        by_vehicle["e-bike-lfp"]["indicator_band"]
        == "BELOW_HISTORICAL_4_16_SUBSET"
    )


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

    assert outcome.result.status == GateStatus.INCONCLUSIVE
    by_id = {e["id"]: e for e in outcome.result.evidence["burner_evaluations"]}
    assert (
        by_id["VENT_EBIKE"]["indicator_band"]
        == "BELOW_HISTORICAL_4_16_SUBSET"
    )
    assert outcome.result.evidence["grid_sensitivity_required"] is True


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

