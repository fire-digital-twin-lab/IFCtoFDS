"""Đối chiếu frame IFC và FDS với điểm neo, bounds và ma trận độc lập."""

import json

import ifcopenshell.geom
import numpy as np
import pytest

from ifc_to_fds.cli import main
from ifc_to_fds.core.federation import load_sources
from ifc_to_fds.core.placement import extract_placement
from ifc_to_fds.core.units import get_length_unit_scale


def test_skew_reference_direction_agrees_with_native_wall(tiny_ifc):
    _, file, wall = tiny_ifc
    axis = wall.ObjectPlacement.RelativePlacement
    axis.Axis = file.createIfcDirection((0.0, 0.0, 1.0))
    axis.RefDirection = file.createIfcDirection((1.0, 0.0, 1.0))

    evidence = extract_placement(wall, 1.0)
    assert evidence["status"] == "CONFIRMED"
    matrix = np.array(evidence["ifc_local_to_model"]).reshape(4, 4)
    native = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), wall)
    native_matrix = np.array(native.transformation.matrix).reshape(4, 4, order="F")

    np.testing.assert_allclose(matrix, native_matrix, rtol=0, atol=1e-12)
    np.testing.assert_allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), rtol=0, atol=1e-12)
    assert np.linalg.det(matrix[:3, :3]) == pytest.approx(1.0)


def test_tilted_default_reference_direction_withholds_provenance(tiny_ifc):
    _, file, wall = tiny_ifc
    relative = wall.ObjectPlacement.RelativePlacement
    relative.Axis = file.createIfcDirection((1.0, 1.0, 1.0))
    relative.RefDirection = None

    evidence = extract_placement(wall, 1.0)
    assert evidence["status"] == "UNVERIFIED"
    assert "RefDirection" in evidence["reason"]


def test_context_dependent_length_unit_requires_si_definition(tiny_ifc):
    _, file, _ = tiny_ifc
    dims = file.createIfcDimensionalExponents(1, 0, 0, 0, 0, 0, 0)
    unknown = file.createIfcContextDependentUnit(dims, "LENGTHUNIT", "CUSTOM")
    file.by_type("IfcProject")[0].UnitsInContext.Units = [unknown]
    with pytest.raises(ValueError, match="IFC length unit"):
        get_length_unit_scale(file)


def test_auto_rebase_in_z_updates_storey_and_geometry(tiny_ifc):
    path, file, wall = tiny_ifc
    height = 1_000_000.0
    wall.ObjectPlacement.RelativePlacement.Location.Coordinates = (0.0, 0.0, height)
    storey = file.by_type("IfcBuildingStorey")[0]
    storey.Elevation = height
    file.write(str(path))

    model = load_sources([path])
    assert model.source.rebase_vector == [0.0, 0.0, height]
    assert model.storey_references[0].elevation_m == pytest.approx(0.0)
    element = next(e for e in model.elements if e.ifc_type == "IfcWall")
    assert element.bounding_box.zmin == pytest.approx(0.0)
    matrix = np.array(element.placement["effective_world"]).reshape(4, 4)
    np.testing.assert_allclose(matrix[:3, 3] + model.source.rebase_vector, [0.0, 0.0, height])


def test_cli_bbox_coordinate_frame_with_rebase(tiny_ifc, tmp_path):
    path, _, _ = tiny_ifc
    config = tmp_path / "input.json"
    config.write_text(json.dumps({"rebase_vector": [1001.0, 0.0, 3.0]}), encoding="utf-8")
    result = main([
        "convert", str(path), "-o", str(tmp_path / "room.fds"), "--config", str(config),
        "--bbox", "-1", "3", "-1", "2", "-1", "4",
        "--domain", "-1", "3", "-1", "2", "-1", "4", "--coordinate-frame", "WORLD",
    ])
    assert result == 0
    manifest = json.loads((tmp_path / "room_manifest.json").read_text(encoding="utf-8"))
    assert manifest["configuration"]["scope"]["coordinate_frame"] == "WORLD"
    assert manifest["simulation_domain"]["xmin"] == pytest.approx(-1002.0)


def test_conflicting_declared_map_frames_need_explicit_federation(tiny_ifc, tmp_path):
    path, file, _ = tiny_ifc
    context = file.by_type("IfcGeometricRepresentationContext", include_subtypes=False)[0]
    crs = file.createIfcProjectedCRS("EPSG:32648")
    conversion = file.create_entity(
        "IfcMapConversion",
        SourceCRS=context,
        TargetCRS=crs,
        Eastings=600000.0,
        Northings=2000000.0,
        OrthogonalHeight=40.0,
    )
    file.write(str(path))
    other = tmp_path / "other.ifc"
    conversion.Eastings += 10.0
    file.write(str(other))

    with pytest.raises(ValueError, match="IFC map frames"):
        load_sources([path, other], {"common_coordinates": True})
    transform = np.eye(4)
    transform[0, 3] = 10.0
    result = load_sources(
        [path, other], {"transforms": {"0": np.eye(4).tolist(), "1": transform.tolist()}}
    )
    assert result.sources[1].world_transform[3] == pytest.approx(10.0)


def test_scenario_world_device_and_vehicle_use_base_frame():
    from ifc_to_fds.fire.scenario_request import ScenarioRequest

    request = ScenarioRequest.model_validate({
        "bundle_sha256": "a" * 64,
        "coordinate_frame": "WORLD",
        "ev_selections": [{
            "preset_id": "auto-nmc", "geometry_mode": "PARAMETRIC",
            "position": [600002.0, 2000003.0, 42.0], "floor_z_m": 41.0,
            "ground_clearance_m": 0.2,
        }],
        "devices": [{
            "id": "TC1", "device_type": "SENSOR", "quantity": "TEMPERATURE",
            "position": [600001.0, 2000002.0, 44.0], "setpoint": 80.0,
        }],
    })
    scenario = request.in_base_frame([600000.0, 2000000.0, 40.0])
    assert scenario.coordinate_frame == "REBASED"
    assert scenario.ev_selections[0].position == (2.0, 3.0, 2.0)
    assert scenario.ev_selections[0].floor_z_m == 1.0
    assert scenario.ev_selections[0].ground_clearance_m == 0.2
    assert scenario.devices[0].position == (1.0, 2.0, 4.0)
    assert request.devices[0].position[0] == 600001.0
