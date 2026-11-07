"""P3c regression tests for source placement/orientation provenance."""

import math

import pytest

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.domain.mapping import (
    MappingDecision,
    MappingPlan,
    MappingStrategy,
    build_mapping_plan,
)
from ifc_to_fds.fire.scenario_emitter import EVSelection, emit_fire_scenario
from ifc_to_fds.mapping.exporter import serialize_mapping


def _hash() -> str:
    return "c" * 64


def _placement(
    yaw_degrees: float = 0.0,
    *,
    tilt_degrees: float = 0.0,
    mapped_items: list[dict] | None = None,
) -> dict:
    yaw = math.radians(yaw_degrees)
    tilt = math.radians(tilt_degrees)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cx, sx = math.cos(tilt), math.sin(tilt)

    # Rz(yaw) @ Rx(tilt)
    rotation = [
        [cy, -sy * cx, sy * sx],
        [sy, cy * cx, -cy * sx],
        [0.0, sx, cx],
    ]
    matrix = [
        rotation[0][0], rotation[0][1], rotation[0][2], 0.0,
        rotation[1][0], rotation[1][1], rotation[1][2], 0.0,
        rotation[2][0], rotation[2][1], rotation[2][2], 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    return {
        "status": "CONFIRMED",
        "units": "METRE",
        "matrix_order": "ROW_MAJOR",
        "vector_convention": "COLUMN",
        "effective_world": matrix,
        "mapped_items": mapped_items or [],
    }


def _vehicle_decision(
    bounds: BoundingBox,
    *,
    yaw_degrees: float = 0.0,
    tilt_degrees: float = 0.0,
    placement: dict | None = None,
) -> MappingDecision:
    return MappingDecision(
        entity_key="VEHICLE_1",
        strategy=MappingStrategy.OBST,
        simulation_role="PASSIVE_OBSTACLE",
        fds_representation="OBST",
        representation_bounds=bounds,
        source_ifc_type="IfcBuildingElementProxy",
        source_type_class=None,
        placement=placement
        if placement is not None
        else _placement(yaw_degrees, tilt_degrees=tilt_degrees),
        review_status="APPROVED",
        decision={
            "action": "PASSIVE_OBSTACLE",
            "policy_version": "p3c-test-v1",
            "rationale": "Reviewed vehicle source for orientation provenance",
            "reviewer": "TEST_REVIEWER",
            "evidence": "tests/test_vehicle_orientation_provenance.py",
            "semantic_role": "VEHICLE",
            "factors": {
                "ifc_type": "explicit reviewed source identity",
                "mesh_scale": "source OBST bounds retained",
                "domain_position": "inside test domain",
                "airflow_clearance": "checked by P3a/P3b",
                "system": "not an MEP network member",
                "future_operational_role": "EV scenario source",
                "golden_policy": "P3c software regression only",
            },
        },
    )


def _vehicle_bounds_for_yaw(yaw_degrees: float) -> BoundingBox:
    """Return a 4 m x 2 m OBST whose longitudinal axis agrees with placement X."""
    quarter = int(round(yaw_degrees / 90.0)) % 4
    if quarter in (0, 2):
        return BoundingBox(
            xmin=3.0, xmax=7.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7
        )
    return BoundingBox(
        xmin=4.0, xmax=6.0, ymin=3.0, ymax=7.0, zmin=0.2, zmax=1.7
    )


def _selection(bounds: BoundingBox) -> EVSelection:
    return EVSelection(
        preset_id="auto-nmc",
        position=(
            (bounds.xmin + bounds.xmax) / 2.0,
            (bounds.ymin + bounds.ymax) / 2.0,
            (bounds.zmin + bounds.zmax) / 2.0,
        ),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_1",
        floor_z_m=0.0,
        ground_clearance_m=bounds.zmin,
    )


def test_parametric_geometry_declares_world_axis_orientation():
    bundle = emit_fire_scenario(
        MappingPlan(),
        _hash(),
        [
            EVSelection(
                preset_id="auto-nmc",
                position=(5.0, 5.0, 0.9),
                dimensions=(4.5, 1.8, 1.5),
                geometry_mode="PARAMETRIC",
                floor_z_m=0.0,
                ground_clearance_m=0.15,
            )
        ],
    )
    geometry = bundle.vehicle_geometries[0]
    assert geometry.orientation_status == "PARAMETRIC_WORLD_ALIGNED"
    assert geometry.yaw_degrees == pytest.approx(0.0)


@pytest.mark.parametrize("yaw", [0.0, 90.0, 180.0, 270.0])
def test_ifc_bound_accepts_confirmed_world_axis_quarter_turns(yaw):
    bounds = _vehicle_bounds_for_yaw(yaw)
    plan = MappingPlan(decisions=[_vehicle_decision(bounds, yaw_degrees=yaw)])
    bundle = emit_fire_scenario(plan, _hash(), [_selection(bounds)])
    geometry = bundle.vehicle_geometries[0]

    assert geometry.orientation_status == "IFC_AXIS_ALIGNED_CONFIRMED"
    assert geometry.yaw_degrees == pytest.approx(yaw)
    assert geometry.source_ifc_type == "IfcBuildingElementProxy"
    assert geometry.provenance["placement_status"] == "CONFIRMED"
    assert (
        geometry.provenance["orientation_method"]
        == "CONFIRMED_EFFECTIVE_WORLD_QUARTER_TURN_WITH_OBST_AXIS_CROSSCHECK"
    )


def test_ifc_bound_rejects_object_placement_that_disagrees_with_verified_long_axis():
    # A swept-solid/item-level 90 degree rotation can leave ObjectPlacement at 0
    # while rotating the actual body. The verified OBST is long in Y, so a 0-degree
    # placement cannot prove vehicle yaw and must fail closed.
    bounds = _vehicle_bounds_for_yaw(90.0)
    decision = _vehicle_decision(bounds, yaw_degrees=0.0)
    with pytest.raises(ValueError, match="disagrees with verified OBST longitudinal axis"):
        emit_fire_scenario(
            MappingPlan(decisions=[decision]),
            _hash(),
            [_selection(bounds)],
        )


def test_ifc_bound_rejects_square_footprint_as_orientation_ambiguous():
    bounds = BoundingBox(
        xmin=3.0, xmax=5.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7
    )
    decision = _vehicle_decision(bounds, yaw_degrees=0.0)
    with pytest.raises(ValueError, match="longitudinal axis is ambiguous"):
        emit_fire_scenario(
            MappingPlan(decisions=[decision]),
            _hash(),
            [_selection(bounds)],
        )


def test_ifc_bound_rejects_missing_or_unconfirmed_placement():
    bounds = BoundingBox(
        xmin=3.0, xmax=7.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7
    )
    missing = _vehicle_decision(bounds, placement={})
    with pytest.raises(ValueError, match="CONFIRMED source placement provenance"):
        emit_fire_scenario(
            MappingPlan(decisions=[missing]),
            _hash(),
            [_selection(bounds)],
        )

    unverified = _vehicle_decision(
        bounds,
        placement={"status": "UNVERIFIED", "reason": "fixture"},
    )
    with pytest.raises(ValueError, match="CONFIRMED source placement provenance"):
        emit_fire_scenario(
            MappingPlan(decisions=[unverified]),
            _hash(),
            [_selection(bounds)],
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("units", "MILLIMETRE", "requires units=METRE"),
        ("matrix_order", "COLUMN_MAJOR", "requires matrix_order=ROW_MAJOR"),
        ("vector_convention", "ROW", "requires vector_convention=COLUMN"),
    ],
)
def test_ifc_bound_rejects_ambiguous_placement_conventions(field, value, message):
    bounds = BoundingBox(
        xmin=3.0, xmax=7.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7
    )
    placement = _placement()
    placement[field] = value
    decision = _vehicle_decision(bounds, placement=placement)

    with pytest.raises(ValueError, match=message):
        emit_fire_scenario(
            MappingPlan(decisions=[decision]),
            _hash(),
            [_selection(bounds)],
        )


def test_ifc_bound_rejects_non_axis_aligned_yaw():
    bounds = BoundingBox(
        xmin=3.0, xmax=7.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7
    )
    decision = _vehicle_decision(bounds, yaw_degrees=45.0)
    with pytest.raises(ValueError, match="yaw is not world-axis-aligned"):
        emit_fire_scenario(
            MappingPlan(decisions=[decision]),
            _hash(),
            [_selection(bounds)],
        )


def test_ifc_bound_rejects_tilt_without_oriented_geom_evidence():
    bounds = BoundingBox(
        xmin=3.0, xmax=7.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7
    )
    decision = _vehicle_decision(bounds, tilt_degrees=5.0)
    with pytest.raises(ValueError, match="tilt is unsupported"):
        emit_fire_scenario(
            MappingPlan(decisions=[decision]),
            _hash(),
            [_selection(bounds)],
        )


def test_ifc_bound_rejects_mapped_item_orientation_until_composition_is_proven():
    bounds = BoundingBox(
        xmin=3.0, xmax=7.0, ymin=4.0, ymax=6.0, zmin=0.2, zmax=1.7
    )
    placement = _placement(
        mapped_items=[
            {
                "step_id": 10,
                "mapping_source_step_id": 20,
                "matrix": _placement(90.0)["effective_world"],
            }
        ]
    )
    decision = _vehicle_decision(bounds, placement=placement)
    with pytest.raises(ValueError, match="mapped-item transforms is not yet supported"):
        emit_fire_scenario(
            MappingPlan(decisions=[decision]),
            _hash(),
            [_selection(bounds)],
        )


def test_mapping_plan_carries_source_identity_and_placement_and_rejects_spoofing(
    box_model,
):
    plan = build_mapping_plan(box_model)
    entity = box_model.elements[0]
    decision = plan.get_decision(entity.entity_key)
    assert decision is not None
    assert decision.source_ifc_type == entity.ifc_type
    assert decision.source_type_class == entity.type_class
    assert decision.placement == entity.placement

    tampered = plan.model_copy(deep=True)
    tampered_decision = tampered.get_decision(entity.entity_key)
    assert tampered_decision is not None
    tampered_decision.placement = {"status": "CONFIRMED", "effective_world": [1.0] * 16}
    with pytest.raises(ValueError, match="placement provenance differs"):
        serialize_mapping(box_model, mapping_plan=tampered)



def test_real_ifc_quarter_turn_orientation_survives_verified_base_round_trip(
    tmp_path,
):
    import json

    import ifcopenshell.api.aggregate
    import ifcopenshell.api.context
    import ifcopenshell.api.geometry
    import ifcopenshell.api.project
    import ifcopenshell.api.root
    import ifcopenshell.api.spatial
    import ifcopenshell.api.unit
    import numpy as np

    from ifc_to_fds.adapters.jobs.base_integrity import verify_accepted_mapping_base
    from ifc_to_fds.adapters.jobs.evidence_index import write_evidence_index
    from ifc_to_fds.application.services.scenario_base import load_verified_base
    from ifc_to_fds.core.inventory import compute_file_sha256
    from ifc_to_fds.pipeline import convert, save_artifacts
    from ifc_to_fds.results import public_result

    file = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcProject", name="P3c Orientation"
    )
    ifcopenshell.api.unit.assign_unit(
        file, units=[ifcopenshell.api.unit.add_si_unit(file, unit_type="LENGTHUNIT")]
    )
    context = ifcopenshell.api.context.add_context(file, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        file,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )
    storey = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcBuildingStorey", name="Ground"
    )
    storey.Elevation = 0.0
    ifcopenshell.api.aggregate.assign_object(
        file, products=[storey], relating_object=project
    )
    vehicle = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcBuildingElementProxy", name="Reviewed EV"
    )
    ifcopenshell.api.spatial.assign_container(
        file, products=[vehicle], relating_structure=storey
    )
    representation = ifcopenshell.api.geometry.add_wall_representation(
        file,
        context=body,
        length=4.0,
        height=1.5,
        thickness=2.0,
    )
    ifcopenshell.api.geometry.assign_representation(
        file, product=vehicle, representation=representation
    )
    matrix = np.eye(4)
    matrix[:3, :3] = np.array(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    matrix[:3, 3] = np.array([6.0, 4.0, 0.2])
    ifcopenshell.api.geometry.edit_object_placement(
        file, product=vehicle, matrix=matrix
    )

    path = tmp_path / "p3c-vehicle-90.ifc"
    file.write(str(path))
    source_hash = compute_file_sha256(str(path))
    entity_key = f"{source_hash}:{vehicle.id()}"

    policy = {
        "action": "PASSIVE_OBSTACLE",
        "policy_version": "p3c-real-ifc-v1",
        "rationale": "Reviewed IFC proxy as EV for P3c orientation round-trip",
        "reviewer": "TEST_REVIEWER",
        "evidence": "tests/test_vehicle_orientation_provenance.py",
        "semantic_role": "VEHICLE",
        "factors": {
            "ifc_type": "IfcBuildingElementProxy reviewed explicitly",
            "mesh_scale": "source solid retained",
            "domain_position": "full-model domain",
            "airflow_clearance": "checked by scenario geometry contract",
            "system": "not an MEP network member",
            "future_operational_role": "EV fire scenario source",
            "golden_policy": "P3c real IFC regression",
        },
    }
    base = tmp_path / "base-p3c"
    result = convert(
        [str(path)],
        configuration={"decisions": {entity_key: policy}},
        output_directory=base,
    )
    assert result["mapping_status"] == "MAPPING_VERIFIED"
    save_artifacts(result, base / "model.fds")
    public = public_result(result, directory=base)
    (base / "result.json").write_text(json.dumps(public), encoding="utf-8")
    write_evidence_index(base, "convert", public)

    digest = result["manifest"]["bundle_sha256"]
    _, plan, manifest = load_verified_base(
        tmp_path,
        digest,
        verify_candidate=verify_accepted_mapping_base,
    )
    decision = plan.get_decision(entity_key)
    assert decision is not None
    assert decision.source_ifc_type == "IfcBuildingElementProxy"
    assert decision.placement["status"] == "CONFIRMED"
    assert decision.placement == next(
        record.placement for record in manifest.records if record.entity_key == entity_key
    )

    bounds = decision.representation_bounds or decision.element_bounds
    assert bounds is not None
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(
            (bounds.xmin + bounds.xmax) / 2.0,
            (bounds.ymin + bounds.ymax) / 2.0,
            (bounds.zmin + bounds.zmax) / 2.0,
        ),
        geometry_mode="IFC_BOUND",
        source_entity_key=entity_key,
        floor_z_m=0.0,
        ground_clearance_m=bounds.zmin,
    )
    bundle = emit_fire_scenario(plan, digest, [selection])
    geometry = bundle.vehicle_geometries[0]

    assert geometry.orientation_status == "IFC_AXIS_ALIGNED_CONFIRMED"
    assert geometry.yaw_degrees == pytest.approx(90.0)
    assert geometry.source_ifc_type == "IfcBuildingElementProxy"
    assert geometry.body_from_verified_base is True
    assert bundle.vehicle_collision_assessments[0].checked_base_entities == 0
