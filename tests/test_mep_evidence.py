import pytest
from ifc_to_fds.mep.classifier import classify_mep_element
from ifc_to_fds.mapping.policy import plan_mapping


@pytest.mark.parametrize("kind", ["IfcPipeSegment", "IfcFlowController", "IfcPump", "IfcBuildingElementProxy"])
def test_name_is_only_a_candidate(kind):
    assert classify_mep_element(kind, "SPRINKLER SMOKE PCCC", "SPR") == ("UNRESOLVED", False)


def test_fire_pipe_requires_structured_evidence():
    assert classify_mep_element("IfcFlowSegment", "cold water", type_class="IfcPipeSegmentType",
                                system_categories=["FIRE_SUPPRESSION"]) == ("FIRE_SUPPRESSION", True)
    assert classify_mep_element("IfcPipeSegment", "pipe", property_sets={
        "Pset_Source": {"SystemClassification": "FIRE_SUPPRESSION"}
    }) == ("FIRE_SUPPRESSION", True)
    assert classify_mep_element("IfcPipeSegment", "pipe", system_categories=[
        "FIRE_SUPPRESSION", "PLUMBING"
    ]) == ("UNRESOLVED", False)


def test_unknown_pipe_remains_reference_geometry(box_model):
    e = box_model.elements[0]
    e.ifc_type, e.type_class = "IfcFlowSegment", "IfcPipeSegmentType"
    e.mep_category = "UNRESOLVED"
    e.classification_evidence = ["IFC type class: IfcPipeSegmentType"]
    plan_mapping(box_model)
    assert e.simulation_role == "REFERENCE_GEOMETRY"
    assert e.fds_representation == "NONE"


def test_opening_host_identity_does_not_collide_on_global_id(tiny_ifc):
    import ifcopenshell.api.root
    from ifc_to_fds.core.inventory import extract_inventory

    path, file, first = tiny_ifc
    second = ifcopenshell.api.root.create_entity(file, ifc_class="IfcSlab", name="Second")
    second.GlobalId = first.GlobalId
    opening = ifcopenshell.api.root.create_entity(file, ifc_class="IfcOpeningElement", name="Void")
    relation = file.create_entity("IfcRelVoidsElement", GlobalId=ifcopenshell.guid.new(),
                                 RelatingBuildingElement=first, RelatedOpeningElement=opening)
    file.write(str(path))
    model, _ = extract_inventory(str(path))
    by_step = {e.step_id: e for e in model.elements}
    assert not by_step[second.id()].openings
    ref = by_step[first.id()].openings[0]
    assert ref.host_entity_key == by_step[first.id()].entity_key
    assert ref.void_relation_key.endswith(f":{relation.id()}")
    assert ref.entity_key == by_step[opening.id()].entity_key
