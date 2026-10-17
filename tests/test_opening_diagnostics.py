from ifc_to_fds.geometry.diagnostics import inspect_host_openings
from ifc_to_fds.application.use_cases.audit_conversion import prepare_model
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation.engine import run_independent_validation


def test_malformed_source_opening_is_explicit_not_bypassed(tiny_ifc):
    import ifcopenshell.api.root

    path, f, wall = tiny_ifc
    opening = ifcopenshell.api.root.create_entity(
        f, ifc_class="IfcOpeningElement", name="Invalid void"
    )
    opening.ObjectPlacement = wall.ObjectPlacement
    # A zero-area closed profile cannot form a solid. Independent source fixture,
    # analogous to a real host with an opening that the kernel cannot construct.
    curve = f.create_entity(
        "IfcPolyline",
        Points=[
            f.create_entity("IfcCartesianPoint", Coordinates=(x, 0.0))
            for x in (0.0, 1.0, 2.0, 0.0)
        ],
    )
    profile = f.create_entity(
        "IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=curve
    )
    origin = f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)),
    )
    solid = f.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=origin,
        ExtrudedDirection=f.create_entity(
            "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
        ),
        Depth=1.0,
    )
    representation = f.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=wall.Representation.Representations[0].ContextOfItems,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )
    opening.Representation = f.create_entity(
        "IfcProductDefinitionShape", Representations=[representation]
    )
    f.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=wall,
        RelatedOpeningElement=opening,
    )
    f.write(str(path))
    evidence = inspect_host_openings(str(path), wall.id())
    assert evidence["errors"][0]["step_id"] == opening.id()
    assert evidence["errors"][0]["stage"] == "IFC_GEOMETRY"
    model = prepare_model([str(path)], {}, reference=True)
    host = next(e for e in model.elements if e.step_id == wall.id())
    assert host.mapping_status == "UNSUPPORTED"
    assert host.fds_representation == "NONE"
    assert host.openings[0].extraction_diagnostic
    text, manifest = serialize_fds(model)
    report = run_independent_validation(model, text, manifest)
    assert report.gates["openings"].status == "INCONCLUSIVE"
    assert any(
        x.category == "openings" and x.element_id == host.entity_key
        for x in report.findings
    )
    assert report.status != "MAPPING_VERIFIED"
