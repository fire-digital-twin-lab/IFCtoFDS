"""P3b regression tests for scientific vehicle-to-base collision gating."""

import pytest

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.domain.mapping import MappingDecision, MappingPlan, MappingStrategy
from ifc_to_fds.fire.scenario_emitter import EVSelection, emit_fire_scenario
from ifc_to_fds.fire.vehicle_geometry import BatteryPack


def _hash() -> str:
    return "b" * 64


def _decision(
    entity_key: str,
    bounds: BoundingBox | None,
    *,
    representation: str = "OBST",
    semantic_role: str | None = None,
) -> MappingDecision:
    payload = {}
    review_status = "NOT_REQUIRED"
    if semantic_role is not None:
        payload = {
            "action": "PASSIVE_OBSTACLE",
            "policy_version": "p3b-test-v1",
            "rationale": f"Reviewed {semantic_role.lower()} source for P3b",
            "reviewer": "TEST_REVIEWER",
            "evidence": "tests/test_vehicle_collision_gate.py",
            "semantic_role": semantic_role,
            "factors": {
                "ifc_type": "reviewed source identity",
                "mesh_scale": "source solid retained",
                "domain_position": "inside test domain",
                "airflow_clearance": "checked by P3b",
                "system": "not an MEP network member",
                "future_operational_role": "EV fire scenario geometry",
                "golden_policy": "P3b software regression only",
            },
        }
        review_status = "APPROVED"
    strategy = MappingStrategy.OBST if representation == "OBST" else MappingStrategy.GEOM
    return MappingDecision(
        entity_key=entity_key,
        strategy=strategy,
        simulation_role="PASSIVE_OBSTACLE",
        fds_representation=representation,
        representation_bounds=bounds,
        review_status=review_status,
        decision=payload,
    )


def _parametric_selection() -> EVSelection:
    return EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.95),
        dimensions=(4.0, 2.0, 1.5),
        geometry_mode="PARAMETRIC",
        floor_z_m=0.0,
        ground_clearance_m=0.2,
    )


def test_legacy_does_not_enable_new_base_collision_gate():
    wall = _decision(
        "WALL_OVERLAP",
        BoundingBox(xmin=4.0, xmax=6.0, ymin=4.0, ymax=6.0, zmin=0.0, zmax=2.0),
    )
    bundle = emit_fire_scenario(
        MappingPlan(decisions=[wall]),
        _hash(),
        [EVSelection(preset_id="auto-nmc", position=(5.0, 5.0, 0.75))],
    )
    assert bundle.vehicle_collision_assessments == []


def test_parametric_vehicle_records_positive_clearance_to_verified_obst():
    wall = _decision(
        "WALL_EAST",
        BoundingBox(xmin=8.0, xmax=8.5, ymin=0.0, ymax=10.0, zmin=0.0, zmax=3.0),
    )
    bundle = emit_fire_scenario(
        MappingPlan(decisions=[wall]),
        _hash(),
        [_parametric_selection()],
    )

    assessment = bundle.vehicle_collision_assessments[0]
    assert assessment.status == "PASS"
    assert assessment.checked_base_entities == 1
    assert assessment.checked_obst_entities == 1
    assert assessment.checked_geom_entities == 0
    assert assessment.nearest_entity_key == "WALL_EAST"
    assert assessment.minimum_aabb_clearance_m == pytest.approx(1.0)


@pytest.mark.parametrize(
    "wall_bounds",
    [
        BoundingBox(xmin=6.9, xmax=8.0, ymin=4.5, ymax=5.5, zmin=0.0, zmax=2.0),
        BoundingBox(xmin=7.0, xmax=8.0, ymin=4.5, ymax=5.5, zmin=0.0, zmax=2.0),
    ],
)
def test_parametric_vehicle_rejects_obst_overlap_or_contact(wall_bounds):
    plan = MappingPlan(decisions=[_decision("WALL_BLOCKING", wall_bounds)])
    with pytest.raises(ValueError, match="collision/contact with verified base OBST"):
        emit_fire_scenario(plan, _hash(), [_parametric_selection()])


def test_parametric_vehicle_uses_vertical_clearance_for_floor_like_obst():
    floor = _decision(
        "FLOOR_SLAB",
        BoundingBox(xmin=0.0, xmax=10.0, ymin=0.0, ymax=10.0, zmin=-0.3, zmax=0.0),
    )
    bundle = emit_fire_scenario(
        MappingPlan(decisions=[floor]),
        _hash(),
        [_parametric_selection()],
    )
    assessment = bundle.vehicle_collision_assessments[0]
    assert assessment.minimum_aabb_clearance_m == pytest.approx(0.2)
    assert assessment.nearest_entity_key == "FLOOR_SLAB"


def test_geom_aabb_overlap_fails_closed_without_exact_mesh_oracle():
    geom = _decision(
        "COLUMN_GEOM",
        BoundingBox(xmin=6.5, xmax=7.5, ymin=4.5, ymax=5.5, zmin=0.0, zmax=2.0),
        representation="GEOM",
    )
    with pytest.raises(ValueError, match="clearance against verified base GEOM is INCONCLUSIVE"):
        emit_fire_scenario(MappingPlan(decisions=[geom]), _hash(), [_parametric_selection()])


def test_disjoint_geom_aabb_proves_separation_at_p3b_scope():
    geom = _decision(
        "GEOM_REMOTE",
        BoundingBox(xmin=9.0, xmax=10.0, ymin=4.0, ymax=6.0, zmin=0.0, zmax=2.0),
        representation="GEOM",
    )
    bundle = emit_fire_scenario(
        MappingPlan(decisions=[geom]),
        _hash(),
        [_parametric_selection()],
    )
    assessment = bundle.vehicle_collision_assessments[0]
    assert assessment.checked_geom_entities == 1
    assert assessment.minimum_aabb_clearance_m == pytest.approx(2.0)


def test_ifc_bound_excludes_own_vehicle_and_battery_sources_only():
    vehicle = BoundingBox(xmin=3.0, xmax=7.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7)
    battery = BoundingBox(xmin=4.0, xmax=6.0, ymin=4.5, ymax=5.5, zmin=0.2, zmax=0.35)
    wall = BoundingBox(xmin=8.0, xmax=8.5, ymin=0.0, ymax=10.0, zmin=0.0, zmax=3.0)
    plan = MappingPlan(
        decisions=[
            _decision("VEHICLE_1", vehicle, semantic_role="VEHICLE"),
            _decision("BATTERY_1", battery, semantic_role="BATTERY_PACK"),
            _decision("WALL_EAST", wall),
        ]
    )
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.95),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_1",
        floor_z_m=0.0,
        ground_clearance_m=0.2,
        battery_geometry=BatteryPack(source_entity_key="BATTERY_1"),
    )

    bundle = emit_fire_scenario(plan, _hash(), [selection])
    assessment = bundle.vehicle_collision_assessments[0]

    assert assessment.excluded_entity_keys == ["BATTERY_1", "VEHICLE_1"]
    assert assessment.checked_base_entities == 1
    assert assessment.nearest_entity_key == "WALL_EAST"
    assert assessment.minimum_aabb_clearance_m == pytest.approx(1.0)


def test_ifc_bound_rejects_collision_with_another_verified_vehicle_body():
    vehicle = BoundingBox(xmin=3.0, xmax=7.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7)
    other = BoundingBox(xmin=6.5, xmax=9.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7)
    plan = MappingPlan(
        decisions=[
            _decision("VEHICLE_1", vehicle, semantic_role="VEHICLE"),
            _decision("VEHICLE_2", other, semantic_role="VEHICLE"),
        ]
    )
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.95),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_1",
        floor_z_m=0.0,
    )

    with pytest.raises(ValueError, match="entity_key=VEHICLE_2"):
        emit_fire_scenario(plan, _hash(), [selection])


def test_emitting_base_entity_without_bounds_fails_closed():
    plan = MappingPlan(decisions=[_decision("BROKEN_OBST", None)])
    with pytest.raises(ValueError, match="has no bounds for collision gate"):
        emit_fire_scenario(plan, _hash(), [_parametric_selection()])
