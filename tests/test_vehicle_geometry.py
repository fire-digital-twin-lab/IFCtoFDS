"""P3a regression tests for vehicle identity and ground-clearance geometry."""

import re

import pytest

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.domain.mapping import MappingDecision, MappingPlan, MappingStrategy
from ifc_to_fds.fire.scenario_emitter import EVSelection, emit_fire_scenario
from ifc_to_fds.fire.vehicle_geometry import BatteryPack


def _hash() -> str:
    return "a" * 64


def _vehicle_decision(
    entity_key: str,
    bounds: BoundingBox,
    *,
    representation: str = "OBST",
) -> MappingDecision:
    return MappingDecision(
        entity_key=entity_key,
        strategy=MappingStrategy.OBST,
        simulation_role="VEHICLE",
        fds_representation=representation,
        representation_bounds=bounds,
    )


def test_legacy_vehicle_geometry_keeps_historical_box_and_roof_burner():
    bundle = emit_fire_scenario(
        MappingPlan(),
        _hash(),
        [EVSelection(preset_id="auto-nmc", position=(5.0, 5.0, 0.75))],
    )

    geometry = bundle.vehicle_geometries[0]
    assert geometry.mode == "LEGACY"
    assert geometry.body_bounds.to_xb() == pytest.approx([2.75, 7.25, 4.1, 5.9, 0.0, 1.5])
    assert geometry.ground_clearance_m is None
    assert "Vehicle geometry mode: LEGACY" in bundle.fds_fragment
    assert re.search(
        r"&OBST ID='OBST_EV_1', XB=2\.75,7\.25,4\.1,5\.9,0,1\.5, SURF_ID='INERT' /",
        bundle.fds_fragment,
    )
    assert re.search(
        r"&VENT ID='VENT_BURNER_1', XB=2\.75,7\.25,4\.1,5\.9,1\.5,1\.5,",
        bundle.fds_fragment,
    )


def test_parametric_vehicle_requires_explicit_positive_ground_clearance():
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.9),
        dimensions=(4.5, 1.8, 1.5),
        geometry_mode="PARAMETRIC",
        floor_z_m=0.0,
        ground_clearance_m=0.15,
    )
    bundle = emit_fire_scenario(MappingPlan(), _hash(), [selection])

    geometry = bundle.vehicle_geometries[0]
    assert geometry.mode == "PARAMETRIC"
    assert geometry.body_bounds.zmin == pytest.approx(0.15)
    assert geometry.body_bounds.zmax == pytest.approx(1.65)
    assert geometry.ground_clearance_m == pytest.approx(0.15)
    assert "Ground clearance: 0.1500 m above floor z=0.0000 m" in bundle.fds_fragment
    assert re.search(
        r"&VENT ID='VENT_BURNER_1', XB=2\.75,7\.25,4\.1,5\.9,0\.15,0\.15,",
        bundle.fds_fragment,
    )
    assert "XB=2.75,7.25,4.1,5.9,1.65,1.65" not in bundle.fds_fragment


def test_parametric_vehicle_rejects_inconsistent_floor_clearance_and_center():
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.75),
        dimensions=(4.5, 1.8, 1.5),
        geometry_mode="PARAMETRIC",
        floor_z_m=0.0,
        ground_clearance_m=0.15,
    )
    with pytest.raises(ValueError, match="position.z is inconsistent"):
        emit_fire_scenario(MappingPlan(), _hash(), [selection])


def test_ifc_bound_vehicle_reuses_verified_base_and_does_not_duplicate_body():
    bounds = BoundingBox(xmin=2.75, xmax=7.25, ymin=4.1, ymax=5.9, zmin=0.2, zmax=1.7)
    plan = MappingPlan(decisions=[_vehicle_decision("VEHICLE_1", bounds)])
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.95),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_1",
        floor_z_m=0.0,
        ground_clearance_m=0.2,
    )

    bundle = emit_fire_scenario(plan, _hash(), [selection])
    geometry = bundle.vehicle_geometries[0]

    assert geometry.mode == "IFC_BOUND"
    assert geometry.source_entity_key == "VEHICLE_1"
    assert geometry.body_from_verified_base is True
    assert geometry.body_bounds == bounds
    assert geometry.ground_clearance_m == pytest.approx(0.2)
    assert "Vehicle source entity_key: VEHICLE_1" in bundle.fds_fragment
    assert "scenario fragment does not duplicate its OBST" in bundle.fds_fragment
    assert "ID='OBST_EV_1'" not in bundle.fds_fragment
    assert re.search(
        r"&VENT ID='VENT_BURNER_1', XB=2\.75,7\.25,4\.1,5\.9,0\.2,0\.2,",
        bundle.fds_fragment,
    )


def test_ifc_bound_vehicle_rejects_missing_or_non_obst_source():
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.95),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_1",
        floor_z_m=0.0,
    )
    with pytest.raises(ValueError, match="not present in MappingPlan"):
        emit_fire_scenario(MappingPlan(), _hash(), [selection])

    bounds = BoundingBox(xmin=2.75, xmax=7.25, ymin=4.1, ymax=5.9, zmin=0.2, zmax=1.7)
    plan = MappingPlan(decisions=[_vehicle_decision("VEHICLE_1", bounds, representation="GEOM")])
    with pytest.raises(ValueError, match="requires an OBST representation"):
        emit_fire_scenario(plan, _hash(), [selection])


def test_ifc_bound_vehicle_rejects_zero_ground_clearance():
    bounds = BoundingBox(xmin=2.75, xmax=7.25, ymin=4.1, ymax=5.9, zmin=0.0, zmax=1.5)
    plan = MappingPlan(decisions=[_vehicle_decision("VEHICLE_1", bounds)])
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.75),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_1",
        floor_z_m=0.0,
    )
    with pytest.raises(ValueError, match="does not preserve positive ground clearance"):
        emit_fire_scenario(plan, _hash(), [selection])


def test_battery_can_bind_to_verified_entity_and_must_stay_inside_vehicle():
    vehicle_bounds = BoundingBox(
        xmin=2.75, xmax=7.25, ymin=4.1, ymax=5.9, zmin=0.2, zmax=1.7
    )
    battery_bounds = BoundingBox(
        xmin=3.0, xmax=7.0, ymin=4.25, ymax=5.75, zmin=0.2, zmax=0.35
    )
    plan = MappingPlan(
        decisions=[
            _vehicle_decision("VEHICLE_1", vehicle_bounds),
            _vehicle_decision("BATTERY_1", battery_bounds),
        ]
    )
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.95),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_1",
        floor_z_m=0.0,
        battery_geometry=BatteryPack(source_entity_key="BATTERY_1"),
    )
    bundle = emit_fire_scenario(plan, _hash(), [selection])

    geometry = bundle.vehicle_geometries[0]
    assert geometry.battery_bounds == battery_bounds
    assert geometry.battery_source_entity_key == "BATTERY_1"
    assert "source_entity_key=BATTERY_1" in bundle.fds_fragment

    outside_plan = MappingPlan(
        decisions=[
            _vehicle_decision("VEHICLE_1", vehicle_bounds),
            _vehicle_decision(
                "BATTERY_OUTSIDE",
                BoundingBox(
                    xmin=2.0, xmax=3.0, ymin=4.25, ymax=5.75, zmin=0.2, zmax=0.35
                ),
            ),
        ]
    )
    invalid = selection.model_copy(
        update={"battery_geometry": BatteryPack(source_entity_key="BATTERY_OUTSIDE")}
    )
    with pytest.raises(ValueError, match="Battery bounds must remain within"):
        emit_fire_scenario(outside_plan, _hash(), [invalid])


def test_parametric_battery_requires_explicit_dimensions_and_offset():
    with pytest.raises(ValueError, match="requires both dimensions and center_offset_m"):
        BatteryPack(dimensions=(1.0, 1.0, 0.1))

    battery = BatteryPack(
        dimensions=(3.0, 1.2, 0.15),
        center_offset_m=(0.0, 0.0, -0.5),
    )
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.9),
        dimensions=(4.5, 1.8, 1.5),
        geometry_mode="PARAMETRIC",
        floor_z_m=0.0,
        ground_clearance_m=0.15,
        battery_geometry=battery,
    )
    bundle = emit_fire_scenario(MappingPlan(), _hash(), [selection])
    assert bundle.vehicle_geometries[0].battery_bounds is not None


def test_legacy_rejects_scientific_geometry_fields_instead_of_ignoring_them():
    with pytest.raises(ValueError, match="LEGACY geometry does not accept"):
        EVSelection(
            preset_id="auto-nmc",
            position=(5.0, 5.0, 0.75),
            floor_z_m=0.0,
            ground_clearance_m=0.15,
        )


def test_ifc_bound_rejects_unreviewed_non_vehicle_mapping_role():
    bounds = BoundingBox(xmin=2.75, xmax=7.25, ymin=4.1, ymax=5.9, zmin=0.2, zmax=1.7)
    plan = MappingPlan(
        decisions=[
            MappingDecision(
                entity_key="WALL_1",
                strategy=MappingStrategy.OBST,
                simulation_role="WALL",
                fds_representation="OBST",
                representation_bounds=bounds,
            )
        ]
    )
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.95),
        geometry_mode="IFC_BOUND",
        source_entity_key="WALL_1",
        floor_z_m=0.0,
    )
    with pytest.raises(ValueError, match="simulation_role=VEHICLE"):
        emit_fire_scenario(plan, _hash(), [selection])
