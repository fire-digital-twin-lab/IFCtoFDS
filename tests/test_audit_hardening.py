"""CHID that FDS accepts, and source-defect waivers that only the auditor can grant and every reader sees."""

from copy import deepcopy
from pathlib import Path

import pytest

from ifc_to_fds.domain.mapping import MappingStrategy
from ifc_to_fds.domain.validation import AuditConfig
from ifc_to_fds.geometry.mesh import accepted_source_defects
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import MappingManifest
from ifc_to_fds.pipeline import audit, convert
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.parser import parse_fds
from tests.test_accepted_source_defects import REVIEW, _rule
from tests.test_source_topology_self_intersection import _overlapping_closed_boxes

TINY = str(Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc")


def test_chid_from_a_dotted_file_name_has_no_period(box_model):
    # FDS 6.11.1 stops with "ERROR(108): No periods allowed in CHID".
    box_model.source.filename = "Ham2Tang.v2.ifc"
    fds, _ = serialize_fds(box_model)
    assert "&HEAD CHID='Ham2Tang_v2'" in fds


def test_syntax_check_rejects_a_chid_with_a_period():
    text = "&HEAD CHID='Ham2Tang.v2' /\n&MESH IJK=1,1,1, XB=0,1,0,1,0,1 /\n&TIME T_END=0 /\n&TAIL /\n"
    try:
        parsed = parse_fds(text)
    except ValueError as exc:
        assert "CHID" in str(exc)
    else:
        assert any("CHID" in error for error in parsed.errors)


def test_accepted_defect_is_a_visible_finding_in_the_report(box_model):
    model = _overlapping_closed_boxes(box_model)
    model.elements[0].mapping_strategy = MappingStrategy.GEOM
    model.elements[0].fds_representation = "GEOM"
    fds, manifest = serialize_fds(model)
    with accepted_source_defects(_rule(model)):
        report = run_independent_validation(model, fds, manifest, AuditConfig())
    key = model.elements[0].entity_key
    waived = [f for f in report.findings if f.title == "Source defect accepted by review"]
    assert [f.element_id for f in waived] == [key]
    assert waived[0].severity == "P2" and REVIEW["reviewer"] in waived[0].detail
    assert REVIEW["reviewer"] in report.finalize().to_markdown()


@pytest.fixture(scope="module")
def tiny_conversion(tmp_path_factory):
    result = convert([TINY], output_directory=tmp_path_factory.mktemp("c"))
    assert result["status"] == "MAPPING_VERIFIED"
    return result


def _manifest_with_waiver(result):
    key = next(r["entity_key"] for r in result["manifest"]["records"] if r["ifc_type"] == "IfcWall")
    manifest = deepcopy(result["manifest"])
    manifest["configuration"]["accepted_source_defects"] = {
        key: dict(mesh_sha256="0" * 64, defect="TRIANGLE_CROSSING", **REVIEW)
    }
    return MappingManifest.model_validate(manifest), manifest["configuration"]


def test_artifact_cannot_carry_its_own_waivers(tiny_conversion):
    manifest, _ = _manifest_with_waiver(tiny_conversion)
    _, _, report = audit([TINY], tiny_conversion["fds_text"], manifest, None, tiny_conversion["geometry_package"])
    assert not [f for f in report.findings if "accepted_source_defects" in f.detail]
    assert report.status == "MAPPING_VERIFIED"


def test_auditor_supplied_waivers_are_still_applied(tiny_conversion):
    manifest, configuration = _manifest_with_waiver(tiny_conversion)
    _, _, report = audit([TINY], tiny_conversion["fds_text"], manifest, configuration, tiny_conversion["geometry_package"])
    # The digest is deliberately wrong, so an applied waiver shows up as stale.
    assert any("does not match" in f.detail for f in report.findings)
