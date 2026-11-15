"""FDS 6.11.1 pressure drop through compiled HVAC records against a hand calculation (plan M3.6).

Run with IFCFDS_SOLVER=<fds_openmp.exe> pytest -m solver. The deck comes from the repository's own record writer;
the expected values come from Darcy-Weisbach with Colebrook-White friction and the reviewed loss coefficients,
not from the writer.
"""

import csv
import math
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ifc_to_fds.domain.mep.hvac import DuctSpec, EndpointSpec, HvacDuct, HvacNetworkPlan, HvacNode
from ifc_to_fds.mep.fds_records import render_network

pytestmark = pytest.mark.solver

RHO = 1.2  # kg/m3, air at 20 C; FDS computes 1.194 from the ideal gas law
MU = 1.82e-5
XYZ = (0.5, 0.5, 0.5)  # equal heights keep the ambient hydrostatic offset identical at every node
ROUND = dict(diameter_m=math.sqrt(4 * 0.04 / math.pi))  # 0.04 m2


def colebrook(roughness, diameter, reynolds):
    f = 0.02
    for _ in range(100):
        f = (-2 * math.log10(roughness / (3.7 * diameter) + 2.51 / (reynolds * math.sqrt(f)))) ** -2
    return f


def hand_drop(flow, diameter, length, roughness, loss, area):
    u = flow / area
    f = colebrook(roughness, diameter, RHO * u * diameter / MU)
    return (f * length / diameter + loss) * RHO * u * u / 2


def network(flow, section, loss=None, pipe_length=3.0, roughness=5e-4):
    """ambient -> fan(fixed flow) -> A -> straight pipe -> B -> elbow -> ambient"""
    none = EndpointSpec(kind="AMBIENT", loss=(0.0, 0.0))

    def node(name, ducts, boundary=None):
        return HvacNode(id=name, port_keys=[name], entity_keys=["e_" + name], xyz=XYZ, duct_ids=ducts, boundary=boundary)

    def duct(name, nodes, length, **extra):
        return HvacDuct(id=name, entity_key="e_" + name, node_ids=nodes, length_m=length,
                        spec=DuctSpec(**section, roughness_m=roughness, **extra))

    return HvacNetworkPlan(
        nodes=[node("N_IN", ["FAN"], none), node("N_A", ["FAN", "PIPE"]), node("N_B", ["PIPE", "ELBOW"]),
               node("N_OUT", ["ELBOW"], none)],
        ducts=[duct("FAN", ("N_IN", "N_A"), 1.0, volume_flow_m3_s=flow),
               duct("PIPE", ("N_A", "N_B"), pipe_length),
               duct("ELBOW", ("N_B", "N_OUT"), 0.5, loss=loss)],
    )


def run(plan, tmp_path):
    elements = [SimpleNamespace(entity_key=k, source_id="s", global_id=k, step_id=1, ifc_type="IfcDuctSegment")
                for k in {key for n in plan.nodes for key in n.entity_keys} | {d.entity_key for d in plan.ducts}]
    deck = "\n".join([
        "&HEAD CHID='hv' /", "&MESH IJK=10,10,10, XB=0,1,0,1,0,1 /", "&TIME T_END=30. /", "&DUMP DT_DEVC=1. /",
        *render_network(plan, elements),
        "&DEVC ID='p_a', QUANTITY='NODE PRESSURE', NODE_ID='N_A' /",
        "&DEVC ID='p_out', QUANTITY='NODE PRESSURE', NODE_ID='N_OUT' /",
        "&DEVC ID='q_pipe', QUANTITY='DUCT VOLUME FLOW', DUCT_ID='PIPE' /", "&TAIL /", ""])
    exe = Path(os.environ["IFCFDS_SOLVER"])
    env = {**os.environ, "PATH": os.pathsep.join([str(exe.parent / "mpi"), str(exe.parent), os.environ["PATH"]])}
    (tmp_path / "hv.fds").write_text(deck)
    done = subprocess.run([str(exe), "hv.fds"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300)
    assert "completed successfully" in done.stdout + done.stderr, (done.stdout + done.stderr)[-600:]
    rows = list(csv.reader((tmp_path / "hv_devc.csv").open()))
    last = dict(zip(rows[1], map(float, rows[-1])))
    return last["p_a"] - last["p_out"], last["q_pipe"]


def test_pressure_drop_follows_friction_and_reviewed_loss(tmp_path):
    flow, area, diameter = 0.2, 0.04, ROUND["diameter_m"]
    drop, q = run(network(flow, ROUND, loss=(0.4, 1.2)), tmp_path)
    expected = hand_drop(flow, diameter, 3.0, 5e-4, 0.0, area) + hand_drop(flow, diameter, 0.5, 5e-4, 0.4, area)
    assert q == pytest.approx(flow, rel=0.01)
    assert drop == pytest.approx(expected, rel=0.05), (drop, expected)


def test_reversed_flow_uses_the_reverse_loss(tmp_path):
    flow, area, diameter = 0.2, 0.04, ROUND["diameter_m"]
    drop, q = run(network(-flow, ROUND, loss=(0.4, 1.2)), tmp_path)
    expected = hand_drop(flow, diameter, 3.0, 5e-4, 0.0, area) + hand_drop(flow, diameter, 0.5, 5e-4, 1.2, area)
    assert q == pytest.approx(-flow, rel=0.01)
    assert -drop == pytest.approx(expected, rel=0.05), (drop, expected)


def test_smooth_ducts_have_no_friction_in_fds(tmp_path):
    """ROUGHNESS=0 is frictionless in FDS 6.11.1, not a smooth-pipe Colebrook value; the audit must not hide that."""
    flow = 0.2
    drop, _ = run(network(flow, ROUND, loss=(0.0, 0.0), roughness=0.0), tmp_path)
    assert abs(drop) < 0.2  # Pa; a smooth-pipe friction factor would give about 2 Pa over 3.5 m


def test_rectangular_duct_friction_uses_the_equivalent_round_diameter_not_the_hydraulic_one(tmp_path):
    """FDS takes D = sqrt(4A/pi) from AREA and ignores PERIMETER for friction; textbook practice uses 4A/P.

    For this 0.5 x 0.3 m duct that is a real difference, so a rectangular duct is under-resisted by FDS
    unless the engineer compensates. This test records the behaviour; it does not endorse it.
    """
    flow, area, perimeter = 0.5, 0.15, 1.6
    section = dict(area_m2=area, perimeter_m=perimeter)
    drop, _ = run(network(flow, section, loss=(0.0, 0.0)), tmp_path)
    equivalent = math.sqrt(4 * area / math.pi)
    hydraulic = 4 * area / perimeter
    as_fds = sum(hand_drop(flow, equivalent, length, 5e-4, 0.0, area) for length in (3.0, 0.5))
    textbook = sum(hand_drop(flow, hydraulic, length, 5e-4, 0.0, area) for length in (3.0, 0.5))
    assert drop == pytest.approx(as_fds, rel=0.05), (drop, as_fds)
    assert abs(textbook - drop) / textbook > 0.05, (drop, textbook)
