"""Functional authorization and source-fidelity regressions (not snapshot updates)."""

import pytest

from ifc_to_fds.domain.mapping import MappingStrategy, build_mapping_plan
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.validation.parser import parse_fds


@pytest.mark.parametrize("strategy", [MappingStrategy.OBST, MappingStrategy.GEOM])
def test_plan_cannot_switch_emitting_strategy(box_model, strategy):
    plan_mapping(box_model, force_all_geom=strategy == MappingStrategy.GEOM)
    plan = build_mapping_plan(box_model)
    target = MappingStrategy.GEOM if strategy == MappingStrategy.OBST else MappingStrategy.OBST
    plan.decisions[0].strategy = target
    plan.decisions[0].fds_representation = target.value
    with pytest.raises(ValueError, match="fixture:1: strategy differs from source policy"):
        serialize_fds(box_model, mapping_plan=plan)


def test_serialization_does_not_assign_plan_domain_to_source(box_model):
    box_model.simulation_domain = box_model.model_bounds.model_copy()
    box_model.domain_origin = "EXPLICIT_CONFIGURATION"
    plan = build_mapping_plan(box_model)
    plan.simulation_domain = None
    plan.domain_origin = "UNRESOLVED"
    before = box_model.model_dump()
    serialize_fds(box_model, mapping_plan=plan)
    after = box_model.model_dump()
    for output in (before, after):
        output.pop("exported_bounds")
        for e in output["elements"]:
            e.pop("fds_primitive_ids")
    assert after == before


def test_geom_precision_round_trips_close_vertices(box_model):
    e = box_model.elements[0]
    # A thin closed wall with a 12 micrometre thickness at a nonzero world origin.
    for v in e.mesh.vertices:
        v[0] = 123.1234567890123 + v[0] * 0.000006
    from ifc_to_fds.geometry.mesh import bounds_for_vertices

    e.bounding_box = bounds_for_vertices(e.mesh.vertices)
    box_model.simulation_domain = box_model.model_bounds = e.bounding_box
    plan_mapping(box_model, force_all_geom=True)
    text, _ = serialize_fds(box_model)
    parsed = parse_fds(text)
    assert not parsed.errors
    assert parsed.primitives[0].mesh().vertices == e.mesh.vertices


@pytest.mark.parametrize("failure", ["absent", "open"])
def test_unsupported_source_has_no_fake_geom(box_model, failure):
    e = box_model.elements[0]
    if failure == "absent":
        e.mesh = None
    else:
        e.mesh.faces.pop()
    plan_mapping(box_model)
    assert e.mapping_strategy == "NONE"
    assert e.mapping_status == "UNSUPPORTED"
    assert e.geometry_preservation in ("FAILED", "INCONCLUSIVE")
    text, manifest = serialize_fds(box_model)
    assert not parse_fds(text).primitives
    assert manifest.records[0].mapping_status == "UNSUPPORTED"


def test_pure_serializer_has_separate_assignments(box_model):
    from ifc_to_fds.mapping.exporter import serialize_mapping

    plan = build_mapping_plan(box_model)
    before_model, before_plan = box_model.model_dump(), plan.model_dump()
    result = serialize_mapping(box_model, mapping_plan=plan)
    assert result.primitive_assignments["fixture:1"]
    assert result.manifest.records[0].fds_primitive_ids == result.primitive_assignments["fixture:1"]
    assert box_model.model_dump() == before_model
    assert plan.model_dump() == before_plan


@pytest.mark.parametrize("selected_top", [True, False])
def test_storey_interval_uses_same_building_geometry(box_model, selected_top):
    from ifc_to_fds.domain.bim import StoreyReference
    from ifc_to_fds.domain.scope import SpatialScope
    from ifc_to_fds.geometry.mesh import bounds_for_vertices
    from ifc_to_fds.mapping.scope import apply_spatial_scope

    source = box_model.elements[0]
    source.building_id, source.storey_id = "fixture:building", "fixture:storey"
    crossing = source.model_copy(deep=True)
    crossing.entity_key, crossing.step_id = "fixture:2", 2
    crossing.storey_id = "fixture:other-storey"
    unrelated = source.model_copy(deep=True)
    unrelated.entity_key, unrelated.step_id = "fixture:3", 3
    unrelated.building_id, unrelated.storey_id = "fixture:other-building", "fixture:foreign"
    for v in unrelated.mesh.vertices:
        v[2] += 100
    unrelated.bounding_box = bounds_for_vertices(unrelated.mesh.vertices)
    box_model.elements += [crossing, unrelated]
    box_model.storey_references = [
        StoreyReference(storey_id="fixture:storey", source_id="fixture", building_id=source.building_id, name="Top", elevation_m=0),
        StoreyReference(storey_id="fixture:foreign", source_id="fixture", building_id=unrelated.building_id, name="Top", elevation_m=1),
    ]
    if not selected_top:
        box_model.storey_references.append(StoreyReference(
            storey_id="fixture:upper", source_id="fixture", building_id=source.building_id, name="Upper", elevation_m=4,
        ))
    before = crossing.mesh.model_dump()
    apply_spatial_scope(box_model, SpatialScope(storeys=["fixture:storey"]))
    assert source.scope_decision == "IN_SCOPE"
    assert crossing.scope_decision == "BOUNDARY_RETAINED"
    assert unrelated.scope_decision == "OUT_OF_SCOPE"
    assert crossing.mesh.model_dump() == before


def test_unassigned_crossing_geometry_is_not_lost(box_model):
    from ifc_to_fds.domain.bim import StoreyReference
    from ifc_to_fds.domain.scope import SpatialScope
    from ifc_to_fds.mapping.scope import apply_spatial_scope
    e = box_model.elements[0]
    e.building_id, e.storey_id = "fixture:building", "fixture:top"
    unassigned = e.model_copy(deep=True)
    unassigned.entity_key, unassigned.step_id = "fixture:2", 2
    unassigned.building_id = unassigned.storey_id = None
    box_model.elements.append(unassigned)
    box_model.storey_references = [StoreyReference(
        storey_id=e.storey_id, source_id=e.source_id, building_id=e.building_id, name="Top", elevation_m=0,
    )]
    apply_spatial_scope(box_model, SpatialScope(storeys=[e.storey_id]))
    assert unassigned.scope_decision == "BOUNDARY_RETAINED"
