"""P4c1 regression tests for fail-closed grid-sensitivity contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.fire.grid_sensitivity import (
    GridSensitivityCaseResult,
    GridSensitivityObservation,
    GridSensitivityPlanRequest,
    analyze_grid_sensitivity,
    render_grid_sensitivity_cases,
    resolve_grid_sensitivity_plan,
)
from ifc_to_fds.fire.scenario_emitter import EVSelection
from ifc_to_fds.fire.vehicle_geometry_models import VehicleGeometry
from ifc_to_fds.validation.parser import parse_fds


def _domain() -> BoundingBox:
    return BoundingBox(
        xmin=0.0,
        xmax=10.0,
        ymin=0.0,
        ymax=10.0,
        zmin=0.0,
        zmax=4.0,
    )


def _scenario_fds() -> str:
    return (
        "&HEAD CHID='p4c' /\n"
        "&TIME T_END=0.1 /\n"
        "&MESH ID='BASE', IJK=10,10,4, XB=0,10,0,10,0,4 /\n"
        "&TAIL /\n"
    )


def _bundle() -> SimpleNamespace:
    geometry = VehicleGeometry(
        mode="PARAMETRIC",
        body_bounds=BoundingBox(
            xmin=4.0,
            xmax=6.0,
            ymin=4.0,
            ymax=6.0,
            zmin=1.0,
            zmax=2.0,
        ),
        floor_z_m=0.5,
        ground_clearance_m=0.5,
        battery_bounds=BoundingBox(
            xmin=4.2,
            xmax=5.8,
            ymin=4.2,
            ymax=5.8,
            zmin=1.1,
            zmax=1.3,
        ),
        body_from_verified_base=False,
        orientation_status="PARAMETRIC_WORLD_ALIGNED",
        yaw_degrees=0.0,
    )
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 1.5),
        dimensions=(2.0, 2.0, 1.0),
        geometry_mode="PARAMETRIC",
        floor_z_m=0.5,
        ground_clearance_m=0.5,
    )
    return SimpleNamespace(
        vehicle_geometries=[geometry],
        ev_selections=[selection],
    )


def _request(**updates) -> GridSensitivityPlanRequest:
    payload = {
        "source_vehicle_index": 0,
        "local_region": BoundingBox(
            xmin=3.0,
            xmax=7.0,
            ymin=3.0,
            ymax=7.0,
            zmin=0.0,
            zmax=3.0,
        ),
        "refinement_ratios": (2, 3, 4),
    }
    payload.update(updates)
    return GridSensitivityPlanRequest(**payload)


def _observation(
    value: float,
    *,
    unit: str = "degC",
    metric_id: str = "T_CEILING_MAX",
) -> GridSensitivityObservation:
    return GridSensitivityObservation(
        metric_id=metric_id,
        quantity="TEMPERATURE",
        unit=unit,
        value=value,
        aggregation="MAX",
        location_m=(5.0, 5.0, 2.5),
        time_window_s=(0.0, 60.0),
        source_artifact="case_devc.csv",
        source_sha256="e" * 64,
    )


def _case(
    level: str,
    ratio: int,
    dx: float,
    value: float,
    *,
    invariant: str = "a" * 64,
    fds_hash: str = "b" * 64,
    observation: GridSensitivityObservation | None = None,
) -> GridSensitivityCaseResult:
    return GridSensitivityCaseResult(
        level=level,
        refinement_ratio=ratio,
        local_dx_m=dx,
        scenario_invariant_sha256=invariant,
        fds_sha256=fds_hash,
        observations=[observation or _observation(value)],
    )


def _results() -> list[GridSensitivityCaseResult]:
    return [
        _case("COARSE", 2, 0.5, 100.0, fds_hash="b" * 64),
        _case("MEDIUM", 3, 1.0 / 3.0, 110.0, fds_hash="c" * 64),
        _case("FINE", 4, 0.25, 115.0, fds_hash="d" * 64),
    ]


def test_grid_sensitivity_plan_resolves_three_comparable_mesh_levels():
    plan = resolve_grid_sensitivity_plan(
        _scenario_fds(),
        _bundle(),
        _domain(),
        1.0,
        _request(),
    )

    assert [case.level for case in plan.cases] == ["COARSE", "MEDIUM", "FINE"]
    assert [case.refinement_ratio for case in plan.cases] == [2, 3, 4]
    assert [case.local_dx_m for case in plan.cases] == pytest.approx(
        [0.5, 1.0 / 3.0, 0.25]
    )
    assert len({case.mesh_plan_sha256 for case in plan.cases}) == 3
    assert len({case.mesh_plan.local_region.model_dump_json() for case in plan.cases}) == 1
    assert plan.status == "INCONCLUSIVE"


def test_grid_sensitivity_plan_rejects_non_increasing_ratios():
    with pytest.raises(ValueError, match="strictly increasing"):
        _request(refinement_ratios=(2, 2, 4))
    with pytest.raises(ValueError, match=">= 2"):
        _request(refinement_ratios=(1, 2, 3))


def test_rendered_cases_share_invariant_but_have_distinct_mesh_fds():
    source = _scenario_fds()
    plan = resolve_grid_sensitivity_plan(source, _bundle(), _domain(), 1.0, _request())
    rendered = render_grid_sensitivity_cases(source, plan)

    assert list(rendered) == ["COARSE", "MEDIUM", "FINE"]
    assert len({item["scenario_invariant_sha256"] for item in rendered.values()}) == 1
    assert len({item["fds_sha256"] for item in rendered.values()}) == 3
    for item in rendered.values():
        parsed = parse_fds(item["fds_text"])
        assert not parsed.errors
        assert not parsed.unsupported


def test_render_rejects_scenario_change_after_plan_resolution():
    plan = resolve_grid_sensitivity_plan(
        _scenario_fds(),
        _bundle(),
        _domain(),
        1.0,
        _request(),
    )
    changed = _scenario_fds().replace("T_END=0.1", "T_END=1.0")
    with pytest.raises(ValueError, match="Scenario changed"):
        render_grid_sensitivity_cases(changed, plan)


def test_analysis_reports_descriptive_change_without_convergence_pass():
    evidence = analyze_grid_sensitivity(_results())
    metric = evidence.metrics[0]

    assert evidence.status == "INCONCLUSIVE"
    assert evidence.acceptance_policy == "NOT_DEFINED"
    assert evidence.numerical_uncertainty_status == "NOT_ESTIMATED"
    assert metric.trend == "MONOTONIC"
    assert metric.change_trend == "DECREASING_CHANGE"
    assert metric.coarse_to_medium_delta == pytest.approx(10.0)
    assert metric.medium_to_fine_delta == pytest.approx(5.0)
    assert metric.coarse_to_medium_relative_to_finer == pytest.approx(10.0 / 110.0)
    assert metric.medium_to_fine_relative_to_finer == pytest.approx(5.0 / 115.0)
    assert "cannot establish mesh independence" in evidence.reason


def test_analysis_marks_oscillatory_sequence_without_promoting_pass():
    cases = _results()
    cases[1] = _case("MEDIUM", 3, 1.0 / 3.0, 120.0, fds_hash="c" * 64)
    cases[2] = _case("FINE", 4, 0.25, 110.0, fds_hash="d" * 64)

    evidence = analyze_grid_sensitivity(cases)

    assert evidence.status == "INCONCLUSIVE"
    assert evidence.metrics[0].trend == "OSCILLATORY"


def test_analysis_handles_zero_finer_denominator_without_epsilon_assumption():
    cases = [
        _case("COARSE", 2, 0.5, 2.0, fds_hash="b" * 64),
        _case("MEDIUM", 3, 1.0 / 3.0, 0.0, fds_hash="c" * 64),
        _case("FINE", 4, 0.25, 0.0, fds_hash="d" * 64),
    ]

    metric = analyze_grid_sensitivity(cases).metrics[0]

    assert metric.coarse_to_medium_relative_to_finer is None
    assert metric.medium_to_fine_relative_to_finer is None
    assert metric.trend == "PLATEAU_OR_UNRESOLVED"


def test_analysis_rejects_non_mesh_scenario_drift():
    cases = _results()
    cases[2] = cases[2].model_copy(
        update={"scenario_invariant_sha256": "f" * 64}
    )
    with pytest.raises(ValueError, match="differ outside"):
        analyze_grid_sensitivity(cases)


def test_analysis_rejects_observable_metadata_drift():
    cases = _results()
    cases[2] = _case(
        "FINE",
        4,
        0.25,
        115.0,
        fds_hash="d" * 64,
        observation=_observation(115.0, unit="K"),
    )
    with pytest.raises(ValueError, match="metadata differs"):
        analyze_grid_sensitivity(cases)
