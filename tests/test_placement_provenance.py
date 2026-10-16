import json
import numpy as np
import pytest
from ifc_to_fds.core.federation import load_sources
from ifc_to_fds.geometry.storage import write_package, read_package
from ifc_to_fds.geometry.package import seal, audit_package
from ifc_to_fds.validation.acceptance import AcceptanceReport, AuditConfig


@pytest.mark.parametrize("scale", [1, 0.001, 0.3048, 0.0254])
def test_placement_unit_chain_is_not_applied_twice(tiny_ifc, scale):
    from ifc_to_fds.core.placement import extract_placement, federate_placement
    from ifc_to_fds.core.canonical import CanonicalElement

    product = tiny_ifc[2]
    product.ObjectPlacement.RelativePlacement.Location.Coordinates = (10.0, 20.0, 30.0)
    evidence = extract_placement(product, scale)
    assert evidence["status"] == "CONFIRMED"
    local = np.array(evidence["ifc_local_to_model"]).reshape(4, 4)
    assert np.allclose(local[:3, 3], np.array([10, 20, 30]) * scale)
    element = CanonicalElement(
        global_id="x", step_id=1, ifc_type="IfcWall", placement=evidence
    )
    matrix = np.array([[0, -1, 0, 5], [1, 0, 0, 6], [0, 0, 1, 7], [0, 0, 0, 1.0]])
    federate_placement(element, matrix)
    assert np.allclose(np.array(element.transform).reshape(4, 4), matrix @ local)


def test_rehashed_placement_mutation_has_entity(tiny_ifc, tmp_path):
    model = load_sources([tiny_ifc[0]])
    path = tmp_path / "geometry.json"
    package = write_package(model, path)
    wall = next(e for e in model.elements if e.ifc_type == "IfcWall")
    index = package.index
    index["elements"][wall.entity_key]["placement"]["effective_world"][3] += 2
    path.write_text(json.dumps(seal(index)))
    report = AcceptanceReport()
    audit_package(model, read_package(path), report, AuditConfig())
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(f.element_id == wall.entity_key for f in report.findings)


def test_nested_rotated_placement_and_mapped_origin(tiny_ifc):
    from ifc_to_fds.core.placement import extract_placement

    _, file, wall = tiny_ifc

    def point(xyz):
        return file.create_entity("IfcCartesianPoint", Coordinates=xyz)

    axis = file.create_entity(
        "IfcAxis2Placement3D",
        Location=point((10.0, 20.0, 30.0)),
        RefDirection=file.create_entity(
            "IfcDirection", DirectionRatios=(0.0, 1.0, 0.0)
        ),
    )
    parent = file.create_entity("IfcLocalPlacement", RelativePlacement=axis)
    wall.ObjectPlacement.PlacementRelTo = parent
    wall.ObjectPlacement.RelativePlacement.Location.Coordinates = (2.0, 0.0, 0.0)
    original = wall.Representation.Representations[0]
    origin = file.create_entity("IfcAxis2Placement3D", Location=point((3.0, 0.0, 0.0)))
    source = file.create_entity(
        "IfcRepresentationMap", MappingOrigin=origin, MappedRepresentation=original
    )
    target = file.create_entity(
        "IfcCartesianTransformationOperator3D",
        LocalOrigin=point((7.0, 0.0, 0.0)),
        Scale=1.0,
    )
    item = file.create_entity(
        "IfcMappedItem", MappingSource=source, MappingTarget=target
    )
    mapped = file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=original.ContextOfItems,
        RepresentationIdentifier="Body",
        RepresentationType="MappedRepresentation",
        Items=[item],
    )
    wall.Representation.Representations = [mapped]
    value = extract_placement(wall, 0.001)
    assert value["status"] == "CONFIRMED"
    assert value["chain"] == [wall.ObjectPlacement.id(), parent.id()]
    assert np.allclose(
        np.array(value["ifc_local_to_model"]).reshape(4, 4)[:3, 3],
        [0.010, 0.022, 0.030],
    )
    assert len(value["mapped_items"]) == 1
    assert value["mapped_items"][0]["step_id"] == item.id()
    assert np.allclose(
        np.array(value["mapped_items"][0]["matrix"]).reshape(4, 4)[:3, 3], [0.010, 0, 0]
    )
