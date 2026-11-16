"""HVAC-D1/D2: an audit reports an unsupported VENT as a failed `hvac` gate; it never raises, and convert still refuses."""

import hashlib
import re
from unittest import mock

import pytest

from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.pipeline import audit, convert, prepare
from ifc_to_fds.validation.engine import run_independent_validation
from tests.test_hvac_network import connected_ifc  # noqa: F401  (fixture)

VENT_XB = [1, 1, 1, 1.4, 2, 2.3]  # 0.4 x 0.3 m = 0.12 m2 on the x=1 plane, where no real box has a face
OLD_COMPILER = lambda element: [(0, 1, 0, 4, 0, 4)] if element.ifc_type == "IfcWall" else []  # noqa: E731


def _vent_config(connected_ifc):
    path, config = connected_ifc
    model = prepare([str(path)], config)
    for decision in config["decisions"].values():
        for port, endpoint in decision["hvac"]["endpoints"].items():
            if next(p for e in model.elements for p in e.ports if p.port_key == port).world_position[0] == 1:
                endpoint.update(kind="VENT", vent_xb=VENT_XB)
    return path, config


def test_audit_reports_a_vent_without_a_face_as_hvac_fail_and_convert_still_refuses(connected_ifc, tmp_path):
    path, config = _vent_config(connected_ifc)
    # What the compiler before M6.F2 let through: a deck whose VENT floats in open space.
    with mock.patch("ifc_to_fds.mep.network.emitted_obst_boxes", OLD_COMPILER):
        result = convert([str(path)], config, tmp_path / "old")
    assert result["status"] == "MAPPING_VERIFIED"  # proves the fixture reproduces the escape

    with pytest.raises(ValueError, match="solid/gas face"):
        convert([str(path)], config, tmp_path / "new")

    manifest = MappingManifest.model_validate(result["manifest"])
    _, _, report = audit([str(path)], result["fds_text"], manifest, config, result["geometry_package"])
    gate = report.gates["hvac"]
    assert gate.status == "FAIL" and report.status == "REJECTED"
    assert "0.12 of 0.12 m2 unsupported" in gate.reason and "(1.0, 1.0, 1.0, 1.4, 2.0, 2.3)" in gate.reason
    finding = next(f for f in report.findings if f.id == "HVAC-001")
    assert finding.severity == "P1"


def test_a_deck_with_its_vent_moved_or_removed_fails_the_hvac_gate(connected_ifc):
    """Measured on a VENT on a real wall face: editing the deck is caught by the reviewed-vs-written record compare."""
    path, config = _vent_config(connected_ifc)
    model = prepare([str(path)], {"simulation_domain": config["simulation_domain"]})  # decisions come at plan_mapping
    for e in model.elements:
        if e.ifc_type == "IfcWall":  # one box 0..1 x 0..4 x 0..4, so the x=1 plane is a real face
            e.mesh.vertices = [(min(x, 1.0), y * 20, z) for x, y, z in e.mesh.vertices]
            e.bounding_box.xmax, e.bounding_box.ymax, e.representation_bounds = 1.0, 4.0, None
    plan_mapping(model, decisions=config["decisions"])
    text, manifest = serialize_fds(model)

    def gate(changed):
        manifest.fds_sha256 = hashlib.sha256(changed.encode()).hexdigest()
        manifest.reseal()
        return run_independent_validation(model, changed, manifest).gates["hvac"].status

    assert gate(text) == "PASS"
    vent = re.search(r"&VENT [^\n]*", text).group(0)
    xb = re.search(r"XB=([^,/]*,[^,/]*,[^,/]*,[^,/]*,[^,/]*,[^,/]*)", vent).group(1)
    assert gate(text.replace(vent, vent.replace(xb, "1.0,1.0,2.0,2.4,3.0,3.3"))) == "FAIL"  # into open space
    assert gate(text.replace(vent, vent.replace(xb, "1.0,1.0,2.0,2.4,0.5,0.8"))) == "FAIL"  # moved, port unchanged
    assert gate(text.replace(vent, "")) == "FAIL"
