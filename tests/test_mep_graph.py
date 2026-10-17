import numpy as np
import ifcopenshell.api.root
from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.mep.mep_graph import extract_mep_graph
from ifc_to_fds.mep.classifier import classify_mep_element


def test_classification_precedence():
    assert classify_mep_element("IfcPipeSegment", "water") == ("UNRESOLVED", False)
    assert classify_mep_element("IfcPipeSegment", "pipe", "PCCC") == (
        "UNRESOLVED",
        False,
    )
    assert classify_mep_element("IfcFan", "fan", "SMOKE EXTRACTION") == (
        "VENTILATION",
        False,
    )
    assert classify_mep_element("IfcDuctSegment", "duct") == ("VENTILATION", False)


def test_ifc2x3_explicit_port_ownership(tmp_path):
    import ifcopenshell

    file = ifcopenshell.file(schema="IFC2X3")
    organization = file.create_entity("IfcOrganization", Name="Fixture")
    person = file.create_entity("IfcPerson", Id="fixture")
    user = file.create_entity(
        "IfcPersonAndOrganization", ThePerson=person, TheOrganization=organization
    )
    app = file.create_entity(
        "IfcApplication",
        ApplicationDeveloper=organization,
        Version="1",
        ApplicationFullName="Test fixture",
        ApplicationIdentifier="TEST",
    )
    history = file.create_entity(
        "IfcOwnerHistory",
        OwningUser=user,
        OwningApplication=app,
        ChangeAction="ADDED",
        CreationDate=0,
    )

    def root(kind, **kwargs):
        return file.create_entity(
            kind, GlobalId=ifcopenshell.guid.new(), OwnerHistory=history, **kwargs
        )

    unit = file.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    project = root("IfcProject", Name="IFC2X3 fixture")
    project.UnitsInContext = file.create_entity("IfcUnitAssignment", Units=[unit])
    system = root("IfcSystem", Name="Smoke Extract")
    members = [
        root("IfcFlowSegment", Name="Duct"),
        root("IfcFlowFitting", Name="Elbow"),
    ]
    ports = []
    for member in members:
        point = file.create_entity("IfcCartesianPoint", Coordinates=(1.0, 0.0, 0.0))
        relative = file.create_entity("IfcAxis2Placement3D", Location=point)
        placement = file.create_entity("IfcLocalPlacement", RelativePlacement=relative)
        port = root(
            "IfcDistributionPort",
            Name="Port",
            FlowDirection="SOURCEANDSINK",
            ObjectPlacement=placement,
        )
        root("IfcRelConnectsPortToElement", RelatingPort=port, RelatedElement=member)
        root("IfcRelAssignsToGroup", RelatingGroup=system, RelatedObjects=[member])
        ports.append(port)
    root("IfcRelConnectsPorts", RelatingPort=ports[0], RelatedPort=ports[1])
    path = tmp_path / "ports-ifc2x3.ifc"
    file.write(str(path))
    model, source = extract_inventory(str(path))
    extract_mep_graph(model, source)
    assert len(model.mep_graph.systems) == 1
    assert len(model.mep_graph.connections) == 1
    assert not model.mep_graph.issues
    edge = model.mep_graph.connections[0]
    assert edge.source_element_id == f"{model.source.source_id}:{members[0].id()}"
    assert edge.target_element_id == f"{model.source.source_id}:{members[1].id()}"
    assert edge.distance_meters == 0
    owners = [e for e in model.elements if e.step_id in {x.id() for x in members}]
    assert all(e.mep_category == "UNRESOLVED" and len(e.ports) == 1 for e in owners)
    assert all(np.allclose(e.ports[0].world_position, [1.0, 0.0, 0.0]) for e in owners)


def test_ports_edges_positions_system_deduplication(tiny_ifc):
    path, file, wall = tiny_ifc
    a = ifcopenshell.api.root.create_entity(file, ifc_class="IfcDuctSegment", name="A")
    b = ifcopenshell.api.root.create_entity(file, ifc_class="IfcDuctFitting", name="B")
    a.ObjectPlacement = wall.ObjectPlacement
    b.ObjectPlacement = wall.ObjectPlacement
    system = ifcopenshell.api.root.create_entity(
        file,
        ifc_class="IfcDistributionSystem",
        name="Smoke extract",
        predefined_type="VENTILATION",
    )
    for member in (a, b):
        file.create_entity(
            "IfcRelAssignsToGroup",
            GlobalId=__import__("ifcopenshell").guid.new(),
            RelatedObjects=[member],
            RelatingGroup=system,
        )
    ports = []
    for owner, x in ((a, 1.0), (b, 1.0)):
        port = ifcopenshell.api.root.create_entity(
            file, ifc_class="IfcDistributionPort", name="Port"
        )
        port.FlowDirection = "SOURCEANDSINK"
        point = file.create_entity("IfcCartesianPoint", Coordinates=(x, 0.0, 0.0))
        placement = file.create_entity("IfcAxis2Placement3D", Location=point)
        port.ObjectPlacement = file.create_entity(
            "IfcLocalPlacement",
            PlacementRelTo=owner.ObjectPlacement,
            RelativePlacement=placement,
        )
        file.create_entity(
            "IfcRelNests",
            GlobalId=__import__("ifcopenshell").guid.new(),
            RelatingObject=owner,
            RelatedObjects=[port],
        )
        ports.append(port)
    file.create_entity(
        "IfcRelConnectsPorts",
        GlobalId=__import__("ifcopenshell").guid.new(),
        RelatingPort=ports[0],
        RelatedPort=ports[1],
    )
    file.write(str(path))
    model, source = extract_inventory(str(path))
    extract_mep_graph(model, source)
    assert not model.mep_graph.issues
    assert len(model.mep_graph.systems) == 1
    assert len(model.mep_graph.systems[0].element_keys) == 2
    assert len(model.mep_graph.connections) == 1
    graph = model.mep_graph.model_dump()
    extract_mep_graph(model, source)
    assert graph == model.mep_graph.model_dump(), "Extraction must be idempotent"
    elements = [e for e in model.elements if e.global_id in (a.GlobalId, b.GlobalId)]
    assert all(e.mep_category == "VENTILATION" for e in elements)
    assert all(np.allclose(e.ports[0].world_position, [1, 0, 0]) for e in elements)
    assert elements[0].ports[0].connected_port_ids == [elements[1].ports[0].port_key]
    assert model.mep_graph.connections[0].distance_meters == 0


def test_graph_differences_safe_keys_and_mixed_type_sort():
    from ifc_to_fds.mep.compare import graph_differences

    expected = {
        "systems": [
            {"system_id": "sys-1", "element_keys": [101, "key-202"]},
            {"invalid_no_id": True},
        ]
    }
    actual = {
        "systems": [
            {"system_id": "sys-1", "element_keys": ["key-202", 303]},
        ]
    }
    diffs = graph_differences(expected, actual)
    assert len(diffs) == 1
    assert diffs[0]["relation_key"] == "sys-1"
    assert diffs[0]["entities"] == [101, 303, "key-202"]

