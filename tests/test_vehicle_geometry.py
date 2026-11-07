"""P3a regression tests for vehicle identity and ground-clearance geometry."""

import re

import pytest

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.domain.mapping import MappingDecision, MappingPlan, MappingStrategy
from ifc_to_fds.fire.scenario_emitter import EVSelection, emit_fire_scenario
from ifc_to_fds.fire.vehicle_geometry import BatteryPack
from ifc_to_fds.mapping.policy import plan_mapping, validate_decisions


def _hash() -> str:
    return "a" * 64


def _reviewed_policy(semantic_role: str) -> dict:
    return {
        "action": "PASSIVE_OBSTACLE",
        "policy_version": "p3a-test-v1",
        "rationale": f"Reviewed {semantic_role.lower()} geometry for P3a regression",
        "reviewer": "TEST_REVIEWER",
        "evidence": "tests/test_vehicle_geometry.py",
        "semantic_role": semantic_role,
        "factors": {
            "ifc_type": "reviewed source identity",
            "mesh_scale": "source solid retained",
            "domain_position": "inside test domain",
            "airflow_clearance": "ground clearance checked separately",
            "system": "not an MEP network member",
            "future_operational_role": "EV fire scenario host",
            "golden_policy": "P3a software regression only",
        },
    }


def _reviewed_vehicle_policy() -> dict:
    return _reviewed_policy("VEHICLE")


def _vehicle_decision(
    entity_key: str,
    bounds: BoundingBox,
    *,
    representation: str = "OBST",
) -> MappingDecision:
    return MappingDecision(
        entity_key=entity_key,
        strategy=MappingStrategy.OBST,
        simulation_role="PASSIVE_OBSTACLE",
        fds_representation=representation,
        representation_bounds=bounds,
        review_status="APPROVED",
        decision=_reviewed_vehicle_policy(),
    )


def _battery_decision(entity_key: str, bounds: BoundingBox) -> MappingDecision:
    return MappingDecision(
        entity_key=entity_key,
        strategy=MappingStrategy.OBST,
        simulation_role="PASSIVE_OBSTACLE",
        fds_representation="OBST",
        representation_bounds=bounds,
        review_status="APPROVED",
        decision=_reviewed_policy("BATTERY_PACK"),
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
    assert "Vehicle geometry mode:" not in bundle.fds_fragment
    assert "Ground clearance:" not in bundle.fds_fragment
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
            _battery_decision("BATTERY_1", battery_bounds),
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
            _battery_decision(
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


def test_ifc_bound_battery_rejects_unreviewed_source_semantics():
    vehicle_bounds = BoundingBox(
        xmin=2.75, xmax=7.25, ymin=4.1, ymax=5.9, zmin=0.2, zmax=1.7
    )
    battery_bounds = BoundingBox(
        xmin=3.0, xmax=7.0, ymin=4.25, ymax=5.75, zmin=0.2, zmax=0.35
    )
    plan = MappingPlan(
        decisions=[
            _vehicle_decision("VEHICLE_1", vehicle_bounds),
            MappingDecision(
                entity_key="BATTERY_UNREVIEWED",
                strategy=MappingStrategy.OBST,
                simulation_role="PASSIVE_OBSTACLE",
                fds_representation="OBST",
                representation_bounds=battery_bounds,
            ),
        ]
    )
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 0.95),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_1",
        floor_z_m=0.0,
        battery_geometry=BatteryPack(source_entity_key="BATTERY_UNREVIEWED"),
    )
    with pytest.raises(ValueError, match="semantic_role=BATTERY_PACK"):
        emit_fire_scenario(plan, _hash(), [selection])


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


def test_ifc_bound_rejects_unreviewed_or_non_vehicle_semantics():
    bounds = BoundingBox(xmin=2.75, xmax=7.25, ymin=4.1, ymax=5.9, zmin=0.2, zmax=1.7)
    plan = MappingPlan(
        decisions=[
            MappingDecision(
                entity_key="WALL_1",
                strategy=MappingStrategy.OBST,
                simulation_role="PASSIVE_OBSTACLE",
                fds_representation="OBST",
                representation_bounds=bounds,
                review_status="NOT_REQUIRED",
                decision={},
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
    with pytest.raises(ValueError, match="reviewed semantic_role=VEHICLE"):
        emit_fire_scenario(plan, _hash(), [selection])



def test_vehicle_semantic_review_is_validated_and_survives_mapping_plan(box_model):
    entity = box_model.elements[0]
    policy = _reviewed_vehicle_policy()
    validate_decisions({entity.entity_key: policy})

    planned = plan_mapping(
        box_model,
        decisions={entity.entity_key: policy},
    )
    from ifc_to_fds.domain.mapping import build_mapping_plan

    plan = build_mapping_plan(planned)
    decision = plan.get_decision(entity.entity_key)
    assert decision is not None
    assert decision.simulation_role == "PASSIVE_OBSTACLE"
    assert decision.review_status == "APPROVED"
    assert decision.decision["semantic_role"] == "VEHICLE"

    invalid = dict(policy)
    invalid["semantic_role"] = "CAR_BY_NAME"
    with pytest.raises(ValueError, match="Unsupported semantic role"):
        validate_decisions({entity.entity_key: invalid})

    invalid_action = dict(policy)
    invalid_action["action"] = "REFERENCE_GEOMETRY"
    invalid_action.pop("factors")
    with pytest.raises(ValueError, match="requires action=PASSIVE_OBSTACLE"):
        validate_decisions({entity.entity_key: invalid_action})


def test_scenario_composer_checks_resolved_ifc_bounds_not_legacy_dimensions():
    from types import SimpleNamespace

    from ifc_to_fds.fire.scenario_composer import compose_scenario

    body = BoundingBox(
        xmin=1.0, xmax=3.0, ymin=1.0, ymax=2.0, zmin=0.2, zmax=1.4
    )
    plan = MappingPlan(decisions=[_vehicle_decision("VEHICLE_COMPACT", body)])
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(2.0, 1.5, 0.8),
        geometry_mode="IFC_BOUND",
        source_entity_key="VEHICLE_COMPACT",
        floor_z_m=0.0,
    )
    bundle = emit_fire_scenario(plan, _hash(), [selection])

    base = (
        "&HEAD CHID='resolved_domain' /\n"
        "&TIME T_END=0.0 /\n"
        "&MESH IJK=20,20,15, XB=0,4,0,4,0,3 /\n"
        "&OBST ID='BASE_VEHICLE', XB=1,3,1,2,0.2,1.4, SURF_ID='INERT' /\n"
        "&TAIL /\n"
    )
    manifest = SimpleNamespace(
        simulation_domain={
            "xmin": 0.0,
            "xmax": 4.0,
            "ymin": 0.0,
            "ymax": 4.0,
            "zmin": 0.0,
            "zmax": 3.0,
        },
        records=[],
    )

    composed = compose_scenario(base, bundle, manifest)
    assert "VENT_BURNER_1" in composed
    # The old composer would reconstruct a 4.5 m auto box around x=2 and
    # incorrectly reject it as extending to x=-0.25.
    assert bundle.vehicle_geometries[0].body_bounds == body

@pytest.mark.solver
def test_p3_underbody_burner_geometry_is_accepted_by_pinned_fds(tmp_path):
    import os
    from pathlib import Path
    import subprocess

    from ifc_to_fds.validation.solver_discovery import resolve_solver_executable

    executable = resolve_solver_executable(os.environ.get("IFCFDS_SOLVER")).executable
    assert executable is not None, "Solver suite requires FDS 6.11.1"
    executable = Path(executable)

    parametric = emit_fire_scenario(
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

    bound_box = BoundingBox(
        xmin=2.75, xmax=7.25, ymin=4.1, ymax=5.9, zmin=0.2, zmax=1.7
    )
    bound_plan = MappingPlan(decisions=[_vehicle_decision("VEHICLE_1", bound_box)])
    ifc_bound = emit_fire_scenario(
        bound_plan,
        _hash(),
        [
            EVSelection(
                preset_id="auto-nmc",
                position=(5.0, 5.0, 0.95),
                geometry_mode="IFC_BOUND",
                source_entity_key="VEHICLE_1",
                floor_z_m=0.0,
            )
        ],
    )

    cases = [
        ("parametric", "", parametric.fds_fragment),
        (
            "ifc_bound",
            "&OBST ID='BASE_VEHICLE', XB=2.75,7.25,4.1,5.9,0.2,1.7, SURF_ID='INERT' /\n",
            ifc_bound.fds_fragment,
        ),
    ]
    for name, base_geometry, fragment in cases:
        case_dir = tmp_path / name
        case_dir.mkdir()
        (case_dir / "input.fds").write_text(
            "&HEAD CHID='vehicle_geometry' /\n"
            "&TIME T_END=0.0 /\n"
            "&MESH IJK=20,20,10, XB=0,10,0,10,0,3 /\n"
            + base_geometry
            + fragment
            + "\n&TAIL /\n",
            encoding="utf-8",
        )
        run = subprocess.run(
            [str(executable), "input.fds"],
            cwd=case_dir,
            capture_output=True,
            text=True,
            timeout=45,
            env={
                **os.environ,
                "OMP_NUM_THREADS": "1",
                "PATH": str(executable.parent / "mpi")
                + os.pathsep
                + os.environ.get("PATH", ""),
            },
        )
        log = run.stdout + run.stderr
        assert run.returncode == 0, log
        assert "completed successfully" in log.lower(), log
        assert "ERROR:" not in log, log
