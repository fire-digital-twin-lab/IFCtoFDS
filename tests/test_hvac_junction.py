"""A tee compiles to one FDS node with reviewed LOSS(i,j) entries; FDS splits the flow as the hand calculation says."""

import copy
import hashlib
import math
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.guid

from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.pipeline import convert, prepare
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.parser import parse_fds

DOMAIN = dict(xmin=0, xmax=10, ymin=0, ymax=5, zmin=0, zmax=5)
# (class, name, placement x, y, z, length, port x positions along the element, extra port at (x, y))
ELEMENTS = (
    ("IfcDuctSegment", "Stem", 1.0, 1.0, 2.0, 3.0, ((0.0, 0.2), (3.0, 0.2))),
    ("IfcDuctFitting", "Tee", 4.0, 1.0, 2.0, 0.5, ((0.0, 0.2), (0.5, 0.2), (0.25, 2.2))),
    ("IfcDuctSegment", "BranchOne", 4.5, 1.0, 2.0, 3.0, ((0.0, 0.2), (3.0, 0.2))),
    ("IfcDuctSegment", "BranchTwo", 4.25, 3.0, 2.0, 3.0, ((0.0, 0.2), (3.0, 0.2))),
)
LINKS = ((0, 1, 1, 0), (1, 1, 2, 0), (1, 2, 3, 0))  # (element, port, element, port) pairs of IfcRelConnectsPorts


def make_tee_ifc(path):
    """Real IFC4: stem duct -> tee -> two branch ducts, joined by explicit port connections."""
    f = ifcopenshell.api.project.create_file(version="IFC4")
    root = ifcopenshell.api.root.create_entity
    project = root(f, ifc_class="IfcProject", name="Tee fixture")
    ifcopenshell.api.unit.assign_unit(f, units=[ifcopenshell.api.unit.add_si_unit(f, unit_type="LENGTHUNIT")])
    context = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(f, context_type="Model", context_identifier="Body",
                                                target_view="MODEL_VIEW", parent=context)
    storey = root(f, ifc_class="IfcBuildingStorey", name="Floor")
    storey.Elevation = 0.0
    ifcopenshell.api.aggregate.assign_object(f, products=[storey], relating_object=project)
    products, port_entities = [], []
    for cls, name, x, y, z, length, port_xy in (("IfcWall", "Wall", 0, 0, 0, 8, ()),) + ELEMENTS:
        item = root(f, ifc_class=cls, name=name)
        ifcopenshell.api.spatial.assign_container(f, products=[item], relating_structure=storey)
        thickness, height = (0.2, 4.0) if cls == "IfcWall" else (0.4, 0.3)
        profile = f.create_entity("IfcRectangleProfileDef", ProfileType="AREA",
                                  Position=f.create_entity("IfcAxis2Placement2D", Location=f.create_entity(
                                      "IfcCartesianPoint", Coordinates=(length / 2.0, thickness / 2.0))),
                                  XDim=float(length), YDim=float(thickness))
        solid = f.create_entity("IfcExtrudedAreaSolid", SweptArea=profile,
                                Position=f.create_entity("IfcAxis2Placement3D", Location=f.create_entity(
                                    "IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))),
                                ExtrudedDirection=f.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
                                Depth=float(height))
        rep = f.create_entity("IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body",
                              RepresentationType="SweptSolid", Items=[solid])
        ifcopenshell.api.geometry.assign_representation(f, product=item, representation=rep)
        matrix = np.eye(4)
        matrix[:3, 3] = [x, y, z]
        ifcopenshell.api.geometry.edit_object_placement(f, product=item, matrix=matrix)
        products.append(item)
        if cls != "IfcWall":
            entities = []
            for px, py in port_xy:
                port = root(f, ifc_class="IfcDistributionPort", name=f"Port {name} {px}")
                port.FlowDirection = "SOURCEANDSINK"
                port.ObjectPlacement = f.create_entity(
                    "IfcLocalPlacement", PlacementRelTo=item.ObjectPlacement,
                    RelativePlacement=f.create_entity("IfcAxis2Placement3D", Location=f.create_entity(
                        "IfcCartesianPoint", Coordinates=(px, py, 0.15))))
                f.create_entity("IfcRelNests", GlobalId=ifcopenshell.guid.new(), RelatingObject=item, RelatedObjects=[port])
                entities.append(port)
            port_entities.append(entities)
    system = root(f, ifc_class="IfcDistributionSystem", name="Supply air", predefined_type="VENTILATION")
    f.create_entity("IfcRelAssignsToGroup", GlobalId=ifcopenshell.guid.new(), RelatedObjects=products[1:], RelatingGroup=system)
    for a, pa, b, pb in LINKS:
        f.create_entity("IfcRelConnectsPorts", GlobalId=ifcopenshell.guid.new(),
                        RelatingPort=port_entities[a][pa], RelatedPort=port_entities[b][pb])
    f.write(str(path))


def reviewed(**hvac):
    return dict(action="HVAC", policy_version="hvac-v1", reviewer="fixture", rationale="fixture", evidence="fixture", hvac=hvac)


def build(tmp_path, ks, stem_flow=0.3, branch_flow=None, edit=None):
    """(ifc path, configuration with decisions, name -> entity_key) for the tee with reviewed pair losses ks."""
    path = tmp_path / "tee.ifc"
    make_tee_ifc(path)
    config = dict(simulation_domain=DOMAIN)
    model = prepare([str(path)], config)
    by_name = {e.name: e for e in model.elements if e.name in {x[1] for x in ELEMENTS}}
    stem, tee, b1, b2 = (by_name[n] for n in ("Stem", "Tee", "BranchOne", "BranchTwo"))
    port = lambda element, x: next(p.port_key for p in element.ports if abs(p.world_position[0] - x) < 1e-6 and (
        element is not tee or abs(p.world_position[1] - (3.2 if x == 4.25 else 1.2)) < 1e-6))
    decisions = {}
    flow = {"Stem": stem_flow, "BranchOne": (branch_flow or (None, None))[0], "BranchTwo": (branch_flow or (None, None))[1]}
    for element, x in ((stem, 1.0), (b1, 7.5), (b2, 7.25)):
        spec = dict(area_m2=0.12, perimeter_m=1.4,
                    endpoints={port(element, x): {"kind": "AMBIENT", "loss": [0.0, 0.0]}})
        if flow[element.name] is not None:
            spec["volume_flow_m3_s"] = flow[element.name]
        decisions[element.entity_key] = reviewed(**spec)
    names = {"a": port(tee, 4.0), "b": port(tee, 4.5), "c": port(tee, 4.25)}
    decisions[tee.entity_key] = reviewed(losses=[dict(from_port=names[a], to_port=names[b], k=k) for (a, b), k in ks.items()])
    if edit:
        edit(decisions, names, model)
    keys = {e.name: e.entity_key for e in (stem, tee, b1, b2)}
    return path, {**config, "decisions": decisions}, keys


K = {("a", "b"): 2.0, ("a", "c"): 0.5, ("b", "a"): 0.3, ("c", "a"): 0.3, ("b", "c"): 1.0, ("c", "b"): 1.0}
BRANCH_OF = {"b": "BranchOne", "c": "BranchTwo", "a": "Stem"}


def test_tee_compiles_to_one_node_with_the_reviewed_losses(tmp_path):
    path, config, keys = build(tmp_path, K)
    result = convert([str(path)], config, tmp_path / "out")
    assert result["status"] == "MAPPING_VERIFIED", result["report"]["findings"]
    assert result["report"]["gates"]["hvac"]["status"] == "PASS"
    parsed = parse_fds(result["fds_text"])
    assert not parsed.errors and not parsed.unsupported
    nodes = [r for r in parsed.operational_records if r.values.get("TYPE_ID") == ["NODE"] and len(r.values["DUCT_ID"]) == 3]
    assert len(nodes) == 1
    node = nodes[0]
    duct_name = {}
    for record in parsed.operational_records:
        if record.values.get("TYPE_ID") == ["DUCT"]:
            owner = record.source["entity_keys"][0]
            duct_name[record.id] = next(name for name, key in keys.items() if key == owner)
    losses = {m.groups(): v[0] for field, v in node.values.items() if (m := re.fullmatch(r"LOSS\((\d+),(\d+)\)", field))}
    ids = node.values["DUCT_ID"]
    got = {(duct_name[ids[int(i) - 1]], duct_name[ids[int(j) - 1]]): k for (i, j), k in losses.items()}
    assert got == {(BRANCH_OF[a], BRANCH_OF[b]): k for (a, b), k in K.items()}
    assert keys["Tee"] in node.source["entity_keys"]  # the junction element owns the node in the manifest


def test_every_ordered_port_pair_needs_a_reviewed_loss(tmp_path):
    path, config, _ = build(tmp_path, {pair: k for pair, k in K.items() if pair != ("c", "b")})
    with pytest.raises(ValueError, match="at least 6 items"):  # three ports have six ordered pairs
        prepare([str(path)], config)


def test_a_junction_loss_cannot_name_a_port_of_another_element(tmp_path):
    def foreign(decisions, names, model):
        tee_key = next(k for k, d in decisions.items() if "losses" in d["hvac"])
        decisions[tee_key]["hvac"]["losses"][0]["to_port"] = "not-a-port"

    path, config, _ = build(tmp_path, K, edit=foreign)
    with pytest.raises(ValueError, match="Unknown port in HVAC junction losses"):
        prepare([str(path)], config)


def test_duplicate_pairs_and_self_loops_are_refused_by_the_spec():
    from ifc_to_fds.domain.mep.hvac import JunctionSpec

    base = [dict(from_port=a, to_port=b, k=1.0) for a in "xyz" for b in "xyz" if a != b]
    JunctionSpec.model_validate(dict(losses=base))
    with pytest.raises(ValueError, match="Duplicate"):
        JunctionSpec.model_validate(dict(losses=base + [dict(from_port="x", to_port="y", k=2.0)]))
    with pytest.raises(ValueError, match="two different ports"):
        JunctionSpec.model_validate(dict(losses=base[:5] + [dict(from_port="x", to_port="x", k=1.0)]))
    with pytest.raises(ValueError):
        JunctionSpec.model_validate(dict(losses=[dict(from_port=x["from_port"], to_port=x["to_port"], k=-1.0) for x in base]))


def test_a_junction_port_without_a_duct_is_refused(tmp_path):
    def drop_branch(decisions, names, model):
        del decisions[next(e.entity_key for e in model.elements if e.name == "BranchTwo")]

    path, config, _ = build(tmp_path, K, edit=drop_branch)
    with pytest.raises(ValueError, match="exactly one duct"):
        prepare([str(path)], config)


def test_a_tee_with_duct_parameters_is_refused(tmp_path):
    def as_duct(decisions, names, model):
        tee_key = next(k for k, d in decisions.items() if "losses" in d["hvac"])
        decisions[tee_key]["hvac"] = dict(area_m2=0.12, perimeter_m=1.4, loss=[0.1, 0.1], length_m=1.0)

    path, config, _ = build(tmp_path, K, edit=as_duct)
    with pytest.raises(ValueError, match="needs reviewed junction losses"):
        prepare([str(path)], config)


def test_node_losses_are_audited_after_the_fds_hash_is_updated(tmp_path):
    path, config, _ = build(tmp_path, K)
    model = prepare([str(path)], config)
    text, manifest = serialize_fds(model)
    changed = re.sub(r"(LOSS\(1,2\)=)[0-9.eE+-]+", r"\g<1>9.0", text, count=1)
    assert changed != text
    manifest.fds_sha256 = hashlib.sha256(changed.encode()).hexdigest()
    manifest.reseal()
    assert run_independent_validation(model, changed, manifest).gates["hvac"].status == "FAIL"


def test_parser_refuses_a_node_loss_outside_the_nodes_ducts():
    deck = ("&HEAD CHID='j' /\n&TIME T_END=0 /\n&MESH IJK=10,10,10, XB=0,1,0,1,0,1 /\n"
            "&HVAC ID='D1', TYPE_ID='DUCT', NODE_ID='A','N', DIAMETER=.2, LENGTH=1 /\n"
            "&HVAC ID='D2', TYPE_ID='DUCT', NODE_ID='N','B', DIAMETER=.2, LENGTH=1 /\n"
            "&HVAC ID='A', TYPE_ID='NODE', DUCT_ID='D1', XYZ=0,0,0, AMBIENT=.TRUE. /\n"
            "&HVAC ID='B', TYPE_ID='NODE', DUCT_ID='D2', XYZ=1,0,0, AMBIENT=.TRUE. /\n"
            "&HVAC ID='N', TYPE_ID='NODE', DUCT_ID='D1','D2', XYZ=0.5,0,0, LOSS(1,3)=1.0 /\n&TAIL /")
    assert any("LOSS(1,3)" in error for error in parse_fds(deck).errors)
    assert not parse_fds(deck.replace("LOSS(1,3)", "LOSS(1,2)")).errors


# ---- FDS 6.11.1: the flow split and the mass balance of the compiled tee (plan M3.6 b) ----

def run_fds(deck, directory):
    exe = Path(os.environ["IFCFDS_SOLVER"])
    env = {**os.environ, "PATH": os.pathsep.join([str(exe.parent / "mpi"), str(exe.parent), os.environ["PATH"]])}
    (directory / "tee.fds").write_text(deck)
    done = subprocess.run([str(exe), "tee.fds"], cwd=directory, env=env, capture_output=True, text=True, timeout=600)
    assert "completed successfully" in done.stdout + done.stderr, (done.stdout + done.stderr)[-600:]
    import csv

    rows = list(csv.reader((directory / "tee_devc.csv").open()))
    return dict(zip(rows[1], map(float, rows[-1])))


def deck_with_flow_probes(tmp_path, config, path, keys):
    result = convert([str(path)], config, tmp_path / "out")
    assert result["status"] == "MAPPING_VERIFIED", result["report"]["findings"]
    parsed = parse_fds(result["fds_text"])
    probes, ids = [], {}
    for record in parsed.operational_records:
        if record.values.get("TYPE_ID") == ["DUCT"]:
            owner = record.source["entity_keys"][0]
            name = next(n for n, key in keys.items() if key == owner)
            ids[name] = record.id
            probes.append(f"&DEVC ID='q_{name}', QUANTITY='DUCT VOLUME FLOW', DUCT_ID='{record.id}' /")
    text = re.sub(r"&TIME[^/]*/", "&TIME T_END=30. /\n&DUMP DT_DEVC=1. /", result["fds_text"], count=1)
    return text.replace("&TAIL /", "\n".join(probes) + "\n&TAIL /")


@pytest.mark.solver
def test_fds_splits_the_flow_as_the_reviewed_losses_say(tmp_path):
    path, config, keys = build(tmp_path, K)  # the stem carries 0.3 m3/s into the tee
    flows = run_fds(deck_with_flow_probes(tmp_path, config, path, keys), tmp_path)
    q1, q2 = flows["q_BranchOne"], flows["q_BranchTwo"]
    # Same area everywhere and no friction: equal pressure drop gives K_i * Q_i^2 equal, K referred to the branch.
    expected_q1 = 0.3 * math.sqrt(K[("a", "c")]) / (math.sqrt(K[("a", "b")]) + math.sqrt(K[("a", "c")]))
    assert q1 + q2 == pytest.approx(0.3, rel=0.01)  # mass is conserved at the node
    assert q1 == pytest.approx(expected_q1, rel=0.05), (q1, q2, expected_q1)
    assert q2 == pytest.approx(0.3 - expected_q1, rel=0.05)


@pytest.mark.solver
def test_fds_merges_two_branches_without_losing_mass(tmp_path):
    path, config, keys = build(tmp_path, K, stem_flow=None, branch_flow=(-0.1, -0.2))
    flows = run_fds(deck_with_flow_probes(tmp_path, config, path, keys), tmp_path)
    assert flows["q_BranchOne"] == pytest.approx(-0.1, rel=0.01)
    assert flows["q_BranchTwo"] == pytest.approx(-0.2, rel=0.01)
    # The stem is oriented from its open end to the tee, so what enters from both branches leaves as -0.3.
    assert flows["q_Stem"] == pytest.approx(-0.3, rel=0.01)


def test_a_four_port_junction_needs_all_twelve_ordered_pairs():
    """The network compiler (not the three-port fixture) checks completeness for larger junctions."""
    from types import SimpleNamespace

    from ifc_to_fds.domain.mep.hvac import JunctionSpec
    from ifc_to_fds.mep.network import _junction

    own = [f"j{i}" for i in range(4)]
    ports = {k: SimpleNamespace(world_position=(float(i), 0.0, 0.0)) for i, k in enumerate(own)}
    owners = {k: "junction" for k in own}
    specs, duct_ids, connections = {}, {}, []
    for i, k in enumerate(own):
        ports[f"d{i}"], owners[f"d{i}"] = SimpleNamespace(world_position=(float(i), 0.0, 0.0)), f"duct{i}"
        specs[f"duct{i}"], duct_ids[f"duct{i}"] = object(), f"D{i}"
        connections.append(SimpleNamespace(source_port_id=k, target_port_id=f"d{i}"))
    model = SimpleNamespace(mep_graph=SimpleNamespace(connections=connections))
    attached = sorted(duct_ids.values())
    pairs = [dict(from_port=a, to_port=b, k=1.0) for a in own for b in own if a != b]
    centre, loss = _junction("junction", JunctionSpec.model_validate(dict(losses=pairs)), ports, owners, specs, duct_ids, attached, model)
    assert len(loss) == 12 and centre == (1.5, 0.0, 0.0)
    with pytest.raises(ValueError, match="missing 1"):
        _junction("junction", JunctionSpec.model_validate(dict(losses=pairs[:-1])), ports, owners, specs, duct_ids, attached, model)
