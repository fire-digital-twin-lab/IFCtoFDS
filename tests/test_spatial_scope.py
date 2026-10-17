import pytest
from ifc_to_fds.core.canonical import ScopeDecision, StoreyReference
from ifc_to_fds.mapping.scope import SpatialScope, apply_spatial_scope
from ifc_to_fds.mapping.policy import plan_mapping, determine_element_strategy
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation.parser import parse_fds


def test_scope_survives_mapping_and_serialization(box_model):
    original = box_model.elements[0]
    outside = original.model_copy(deep=True)
    outside.entity_key = "fixture:2"
    outside.step_id = 2
    outside.global_id = "outside"
    for v in outside.mesh.vertices:
        v[0] += 20
    outside.bounding_box = outside.bounding_box.model_copy(
        update={"xmin": 20.0, "xmax": 22.0}
    )
    box_model.elements.append(outside)
    apply_spatial_scope(box_model, SpatialScope(bounding_box=original.bounding_box))
    assert outside.scope_decision == ScopeDecision.OUT_OF_SCOPE
    plan_mapping(box_model, force_all_geom=True)
    assert outside.mapping_strategy == "EXCLUDED_SCOPE"
    text, manifest = serialize_fds(box_model)
    assert not outside.fds_primitive_ids
    assert all(
        p.source["entity_key"] != "fixture:2" for p in parse_fds(text).primitives
    )
    assert manifest.total_elements_accounted == 2


def test_invalid_or_empty_scope(box_model):
    with pytest.raises(ValueError):
        apply_spatial_scope(box_model, SpatialScope(storeys=["Unknown"]))
    with pytest.raises(ValueError):
        SpatialScope(bounding_box=dict(xmin=1, xmax=0, ymin=0, ymax=1, zmin=0, zmax=1))


def test_ambiguous_storeys(box_model):
    box_model.storey_references = [
        StoreyReference(
            storey_id=f"{source}:1", source_id=source, name="Ground", elevation_m=0
        )
        for source in ("a", "b")
    ]
    with pytest.raises(ValueError, match="ambiguous"):
        apply_spatial_scope(box_model, SpatialScope(storeys=["Ground"]))


def test_rotated_box_is_geom(box_model):
    import numpy as np

    e = box_model.elements[0]
    theta = np.pi / 4
    rotation = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0],
            [np.sin(theta), np.cos(theta), 0],
            [0, 0, 1],
        ]
    )
    e.mesh.vertices = (np.array(e.mesh.vertices) @ rotation.T).tolist()
    assert determine_element_strategy(e) == "GEOM"


def test_failed_geometry_never_semantic(box_model):
    e = box_model.elements[0]
    e.mesh = None
    assert determine_element_strategy(e) == "NONE"


def test_meshless_unselected_source_resolves_out_of_scope(box_model):
    from ifc_to_fds.domain.scope import ScopeDecision
    from ifc_to_fds.domain.bim import CanonicalElement

    box_model.elements[0].source_id = "selected_src"
    box_model.elements[0].storey_id = "selected_src:storey_1"
    box_model.storey_references = [
        StoreyReference(
            storey_id="selected_src:storey_1",
            source_id="selected_src",
            name="Level 1",
            elevation_m=0.0,
        )
    ]
    unselected_element = CanonicalElement(
        global_id="unselected_guid",
        step_id=999,
        ifc_type="IfcWall",
        source_id="unselected_src",
        role="PHYSICAL",
        has_3d_geometry=True,
        mesh=None,
    )
    box_model.elements.append(unselected_element)
    apply_spatial_scope(box_model, SpatialScope(storeys=["Level 1"]))
    assert unselected_element.scope_decision == ScopeDecision.OUT_OF_SCOPE

