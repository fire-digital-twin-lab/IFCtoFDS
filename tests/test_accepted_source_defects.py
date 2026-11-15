"""A reviewer may accept one specific source defect, bound to exact mesh bytes."""

import pytest

from ifc_to_fds.application.dto.configuration import validate_configuration
from ifc_to_fds.domain.mapping import MappingStrategy
from ifc_to_fds.domain.validation import AuditConfig, GateStatus
from ifc_to_fds.geometry.mesh import accepted_source_defects, mesh_digest, self_intersection_evidence
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation import preflight
from ifc_to_fds.validation.engine import run_independent_validation
from tests.test_source_topology_self_intersection import _minimal_fds, _overlapping_closed_boxes

REVIEW = dict(policy_version="1", reviewer="pccc-eng", rationale="Duplicate sub-solid in the authoring tool", evidence="review note 7")


def _rule(model, defect=None):
    mesh = model.elements[0].mesh
    kind = defect or self_intersection_evidence(mesh)["witness"]["kind"]
    return {mesh_digest(mesh): dict(defect=kind, review=dict(REVIEW))}


def test_waiver_applies_only_to_the_exact_mesh_and_defect_kind(box_model):
    model = _overlapping_closed_boxes(box_model)
    mesh = model.elements[0].mesh
    with accepted_source_defects(_rule(model)):
        accepted = self_intersection_evidence(mesh)
    assert accepted["status"] == "ACCEPTED_DEFECT"
    assert accepted["witness"]["kind"] and accepted["mesh_sha256"] == mesh_digest(mesh)
    assert accepted["review"]["reviewer"] == "pccc-eng"
    with accepted_source_defects(_rule(model, "TRIANGLE_CROSSING" if accepted["witness"]["kind"] != "TRIANGLE_CROSSING" else "COPLANAR_FACE_OVERLAP")):
        assert self_intersection_evidence(mesh)["status"] == "CONFIRMED"
    moved = mesh.model_copy(update=dict(vertices=[[x + 1e-9, y, z] for x, y, z in mesh.vertices]))
    with accepted_source_defects(_rule(model)):
        assert self_intersection_evidence(moved)["status"] == "CONFIRMED"
    assert self_intersection_evidence(mesh)["status"] == "CONFIRMED"  # no waiver outside the scope


def test_preflight_reports_digest_and_passes_accepted_defect(box_model):
    model = _overlapping_closed_boxes(box_model)
    key = model.elements[0].entity_key
    fail = preflight.source_topology_preflight(model)[key]
    assert fail["status"] == "FAIL" and fail["mesh_sha256"] == mesh_digest(model.elements[0].mesh)
    with accepted_source_defects(_rule(model)):
        ok = preflight.source_topology_preflight(model)[key]
    assert ok["status"] == "PASS" and ok["reason"] == "ACCEPTED_DEFECT"
    assert key not in preflight.source_topology_blockers({key: ok})


def test_engine_does_not_reject_an_accepted_defect_but_lists_it(box_model):
    model = _overlapping_closed_boxes(box_model)
    model.elements[0].mapping_strategy = MappingStrategy.GEOM
    model.elements[0].fds_representation = "GEOM"
    fds, manifest = serialize_fds(model)
    with accepted_source_defects(_rule(model)):
        report = run_independent_validation(model, fds, manifest, AuditConfig())
    assert not [f for f in report.findings if "self-intersection" in f.detail.lower()]
    assert report.gates["geometry"].status != GateStatus.FAIL
    assert list(report.metrics["accepted_source_defects"]) == [model.elements[0].entity_key]


def test_configuration_schema():
    good = {"E:1": dict(mesh_sha256="a" * 64, defect="TRIANGLE_CROSSING", **REVIEW)}
    assert validate_configuration({"accepted_source_defects": good})["accepted_source_defects"] == good
    for bad in (
        {"E:1": {**good["E:1"], "mesh_sha256": "xyz"}},
        {"E:1": {**good["E:1"], "defect": "SOMETHING"}},
        {"E:1": {k: v for k, v in good["E:1"].items() if k != "reviewer"}},
        {"E:1": {**good["E:1"], "extra": 1}},
        [],
    ):
        with pytest.raises(ValueError, match="accepted_source_defects"):
            validate_configuration({"accepted_source_defects": bad})


def test_stale_acceptance_is_reported_and_not_applied(tmp_path):
    from pathlib import Path

    from ifc_to_fds.pipeline import convert

    tiny = str(Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc")
    clean = convert([tiny], output_directory=tmp_path / "a")
    assert clean["status"] == "MAPPING_VERIFIED"
    key = next(r["entity_key"] for r in clean["manifest"]["records"] if r["ifc_type"] == "IfcWall")
    stale = {key: dict(mesh_sha256="0" * 64, defect="TRIANGLE_CROSSING", **REVIEW)}
    result = convert([tiny], {"accepted_source_defects": stale}, output_directory=tmp_path / "b")
    assert result["status"] == "INCONCLUSIVE"
    assert result["report"]["gates"]["geometry"]["status"] == "INCONCLUSIVE"
    assert any("does not match" in f["detail"] for f in result["report"]["findings"])
