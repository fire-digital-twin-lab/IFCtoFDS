"""Kiểm IFC phụ kiện hai cổng và hệ số tổn thất FDS theo chiều dòng."""

import hashlib
import os
from pathlib import Path
import runpy

import ifcopenshell
from ifcopenshell.api.root import reassign_class
import pytest

from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.pipeline import convert, prepare
from ifc_to_fds.validation.acceptance import AuditConfig
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.parser import parse_fds
from ifc_to_fds.validation.solver import solver_gates
from ifc_to_fds.validation.solver_outputs import load_fds_device_series


@pytest.fixture
def fitting_ifc(tmp_path):
    path = tmp_path / "ducts.ifc"
    factory = runpy.run_path(str(Path(__file__).parents[1] / "scripts/audit-project-logic.py"))
    factory["make_connected_duct_fixture"](path)
    return path


def _configuration(path, mode):
    source = ifcopenshell.open(str(path))
    first = next(e for e in source.by_type("IfcDuctSegment") if e.Name == "Duct A")
    first = reassign_class(source, product=first, ifc_class="IfcDuctFitting",
                           predefined_type="BEND" if mode == "ELBOW" else "TRANSITION")
    source.write(str(path))
    config = {"simulation_domain": dict(xmin=0, xmax=10, ymin=0, ymax=5, zmin=0, zmax=5)}
    model = prepare([str(path)], config)
    decisions = {}
    fitting_key = None
    for e in model.elements:
        if e.ifc_type not in {"IfcDuctFitting", "IfcDuctSegment"}:
            continue
        ports = sorted(e.ports, key=lambda p: p.world_position[0])
        endpoints = {p.port_key: {"kind": "AMBIENT", "loss": (0, 0)} for p in ports if p.world_position[0] in (1.0, 7.0)}
        hvac = dict(area_m2=0.125, perimeter_m=1.5, endpoints=endpoints)
        if e.ifc_type == "IfcDuctFitting":
            fitting_key = e.entity_key
            hvac.update(length_m=3.2, fitting=dict(
                kind=mode, forward_port_keys=[p.port_key for p in ports],
                k=(0.7, 5.0), reference_areas_m2=(0.0625, 0.125),
                source="Fixture reviewed minor-loss data",
            ))
        decisions[e.entity_key] = dict(action="HVAC", policy_version="hvac-v2", reviewer="fixture",
                                       rationale="Explicit topology and reviewed fitting data",
                                       evidence="IFC4 port relationships", hvac=hvac)
    assert fitting_key is not None
    return {**config, "decisions": decisions}, fitting_key


@pytest.mark.parametrize("mode", ["ELBOW", "REDUCER"])
def test_reviewed_fitting_uses_directional_reference_areas_and_survives_ifc_reread(fitting_ifc, tmp_path, mode):
    config, fitting_key = _configuration(fitting_ifc, mode)
    result = convert([str(fitting_ifc)], config, tmp_path / "convert")
    assert result["report"]["gates"]["hvac"]["status"] == "PASS"
    parsed = parse_fds(result["fds_text"])
    assert not parsed.errors and not parsed.unsupported
    duct = next(r for r in parsed.operational_records
                if r.values.get("TYPE_ID") == ["DUCT"] and r.source.get("entity_key") == fitting_key)
    assert duct.values["LOSS"] == pytest.approx([2.8, 5.0])
    assert duct.values["LENGTH"] == [3.2]
    nodes = {r.id: r for r in parsed.operational_records if r.values.get("TYPE_ID") == ["NODE"]}
    assert [nodes[k].values["XYZ"][0] for k in duct.values["NODE_ID"]] == [1, 4]
    assert any("LOSS requires" in error for error in parse_fds(result["fds_text"].replace("LOSS=2.8,5.0", "LOSS=-2.8,5.0")).errors)

    model = prepare([str(fitting_ifc)], config)
    text, manifest = serialize_fds(model)
    changed = text.replace("LOSS=2.8,5.0", "LOSS=5.0,2.8", 1)
    assert changed != text
    manifest.fds_sha256 = hashlib.sha256(changed.encode()).hexdigest()
    manifest.reseal()
    assert run_independent_validation(model, changed, manifest).gates["hvac"].status == "FAIL"


def test_fitting_rejects_unreviewed_loss_or_incomplete_forward_order(fitting_ifc):
    config, key = _configuration(fitting_ifc, "ELBOW")
    parameters = config["decisions"][key]["hvac"]
    data = parameters.pop("fitting")
    with pytest.raises(ValueError, match="reviewed fitting"):
        prepare([str(fitting_ifc)], config)
    parameters["fitting"] = {**data, "forward_port_keys": [data["forward_port_keys"][0], "foreign"]}
    with pytest.raises(ValueError, match="forward.*ports"):
        prepare([str(fitting_ifc)], config)


@pytest.mark.solver
@pytest.mark.parametrize("flow_sign, expected_k", [(1, 2.8), (-1, 5.0)])
def test_pinned_fds_uses_directional_loss_and_conserves_flow(fitting_ifc, tmp_path, flow_sign, expected_k):
    config, fitting_key = _configuration(fitting_ifc, "REDUCER")
    for key, decision in config["decisions"].items():
        if key != fitting_key:
            decision["hvac"]["volume_flow_m3_s"] = 0.25 * flow_sign
    text, _ = serialize_fds(prepare([str(fitting_ifc)], config))
    parsed = parse_fds(text)
    duct = next(r for r in parsed.operational_records
                if r.values.get("TYPE_ID") == ["DUCT"] and r.source.get("entity_key") == fitting_key)
    driver = next(r for r in parsed.operational_records
                  if r.values.get("TYPE_ID") == ["DUCT"] and r.id != duct.id)
    node_a, node_b = duct.values["NODE_ID"]
    head = next(r for r in parsed.records if r.kind == "HEAD")
    time = next(r for r in parsed.records if r.kind == "TIME")
    start, end = time.text_span
    text = text[:start] + "&TIME T_END=0.5, DT=0.025 /" + text[end:]
    driver_flow = f"VOLUME_FLOW={0.25 * flow_sign}"
    assert text.count(driver_flow) == 1
    text = text.replace(driver_flow, driver_flow + ", TAU_VF=0")
    text = text.replace("&TAIL", (
        f"&DEVC ID='k', QUANTITY='DUCT LOSS', DUCT_ID='{duct.id}' /\n"
        f"&DEVC ID='q_fitting', QUANTITY='DUCT VOLUME FLOW', DUCT_ID='{duct.id}' /\n"
        f"&DEVC ID='q_driver', QUANTITY='DUCT VOLUME FLOW', DUCT_ID='{driver.id}' /\n"
        f"&DEVC ID='rho', QUANTITY='DUCT DENSITY', DUCT_ID='{duct.id}' /\n"
        f"&DEVC ID='rho_driver', QUANTITY='DUCT DENSITY', DUCT_ID='{driver.id}' /\n"
        f"&DEVC ID='pa', QUANTITY='NODE PRESSURE', NODE_ID='{node_a}' /\n"
        f"&DEVC ID='pb', QUANTITY='NODE PRESSURE', NODE_ID='{node_b}' /\n&TAIL"
    ))
    solver, _ = solver_gates(text, AuditConfig(
        solver_executable=os.environ.get("IFCFDS_SOLVER"), solver_evidence_directory=str(tmp_path / "solver"),
    ))
    assert solver.status == "PASS", solver.reason
    series = load_fds_device_series(Path(solver.evidence["directory"]), head.values["CHID"][0])
    latest = {key: values.values[-1] for key, values in series.items()}
    assert latest["k"] == pytest.approx(expected_k)
    assert latest["q_fitting"] == pytest.approx(0.25 * flow_sign, rel=0.002)
    assert latest["rho"] * latest["q_fitting"] == pytest.approx(
        latest["rho_driver"] * latest["q_driver"], rel=0.002,
    )
    expected_drop = 0.5 * latest["rho"] * expected_k * (latest["q_fitting"] / 0.125) ** 2
    assert flow_sign * (latest["pa"] - latest["pb"]) == pytest.approx(expected_drop, rel=0.01, abs=0.04)
