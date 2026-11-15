"""Two-port fittings and fixed-flow fans compile only from reviewed values; nothing is inferred from geometry."""

import runpy
from pathlib import Path

import pytest

from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.mep.fds_records import network_records
from ifc_to_fds.mep.network import build_hvac_network
from ifc_to_fds.pipeline import prepare


@pytest.fixture
def model_and_decisions(tmp_path):
    factory = runpy.run_path(str(Path(__file__).parents[1] / "scripts/audit-project-logic.py"))["make_connected_duct_fixture"]
    path = tmp_path / "ducts.ifc"
    factory(path)
    config = {"simulation_domain": dict(xmin=0, xmax=10, ymin=0, ymax=5, zmin=0, zmax=5)}
    model = prepare([str(path)], config)
    decisions = {}
    for duct in [e for e in model.elements if e.ifc_type == "IfcDuctSegment"]:
        endpoints = {p.port_key: {"kind": "AMBIENT"} for p in duct.ports if p.world_position[0] in (1.0, 7.0)}
        decisions[duct.entity_key] = dict(
            action="HVAC", policy_version="hvac-v1", reviewer="fixture", rationale="fixture", evidence="fixture",
            hvac=dict(area_m2=0.12, perimeter_m=1.4, roughness_m=0.0005, endpoints=endpoints),
        )
    return model, decisions


def retype(model, decisions, ifc_type, **hvac):
    """Re-declare the first duct as another kind and give it reviewed parameters."""
    key = sorted(decisions)[0]
    element = next(e for e in model.elements if e.entity_key == key)
    element.ifc_type = element.type_class = ifc_type
    decisions[key]["hvac"].update(hvac)
    return element


def compile_network(model, decisions):
    plan_mapping(model, decisions=decisions)  # plans the mapping, which compiles the network too
    return build_hvac_network(model)


def duct_record(plan, element):
    return next(v for kind, v, keys in network_records(plan) if v["TYPE_ID"] == ["DUCT"] and keys == [element.entity_key])


def test_fitting_without_reviewed_loss_or_length_is_refused(model_and_decisions):
    model, decisions = model_and_decisions
    retype(model, decisions, "IfcDuctFitting")
    with pytest.raises(ValueError, match="reviewed loss coefficients and centreline length"):
        compile_network(model, decisions)


def test_fitting_with_reviewed_loss_emits_it_and_keeps_the_reviewed_length(model_and_decisions):
    model, decisions = model_and_decisions
    element = retype(model, decisions, "IfcDuctFitting", loss=[0.4, 0.4], length_m=3.5)
    record = duct_record(compile_network(model, decisions), element)
    assert record["LOSS"] == [0.4, 0.4] and record["LENGTH"] == [3.5]


def test_asymmetric_loss_needs_port_directions(model_and_decisions):
    model, decisions = model_and_decisions
    retype(model, decisions, "IfcDuctFitting", loss=[0.2, 0.9], length_m=3.5)
    with pytest.raises(ValueError, match="SINK/SOURCE port directions"):
        compile_network(model, decisions)


def test_fan_needs_reviewed_flow_and_port_directions(model_and_decisions):
    model, decisions = model_and_decisions
    element = retype(model, decisions, "IfcFan")
    with pytest.raises(ValueError, match="reviewed volume flow"):
        compile_network(model, decisions)
    decisions[element.entity_key]["hvac"]["volume_flow_m3_s"] = 0.5
    with pytest.raises(ValueError, match="direction is never inferred"):
        compile_network(model, decisions)


def test_fan_flows_from_its_sink_port_to_its_source_port(model_and_decisions):
    model, decisions = model_and_decisions
    element = retype(model, decisions, "IfcFan", volume_flow_m3_s=0.5)
    sink, source = element.ports
    sink.flow_direction, source.flow_direction = "SINK", "SOURCE"
    plan = compile_network(model, decisions)
    duct = next(d for d in plan.ducts if d.entity_key == element.entity_key)
    node_of = {k: n.id for n in plan.nodes for k in n.port_keys}
    assert duct.node_ids == (node_of[sink.port_key], node_of[source.port_key])
    assert duct_record(plan, element)["VOLUME_FLOW"] == [0.5]
    sink.flow_direction, source.flow_direction = "SOURCE", "SINK"
    reversed_duct = next(d for d in build_hvac_network(model).ducts if d.entity_key == element.entity_key)
    assert reversed_duct.node_ids == duct.node_ids[::-1]


def test_negative_loss_is_rejected_by_the_spec():
    from ifc_to_fds.domain.mep.hvac import DuctSpec

    with pytest.raises(ValueError, match="nonnegative"):
        DuctSpec.model_validate(dict(diameter_m=0.2, loss=[-0.1, 0.0]))
