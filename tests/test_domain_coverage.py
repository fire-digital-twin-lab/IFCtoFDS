"""M6.F1: the domain gate must notice MESH records that leave holes in, or overlap within, the declared domain."""

import hashlib
import re

import pytest

from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.mapping.exporter import partition_simulation_domain
from ifc_to_fds.pipeline import audit, convert
from ifc_to_fds.validation.domain_coverage import mesh_coverage_problem

DOMAIN = [0, 2, 0, 1, 0, 3]


def test_two_meshes_sharing_a_face_tile_the_domain():
    assert mesh_coverage_problem([[0, 1, 0, 1, 0, 3], [1, 2, 0, 1, 0, 3]], DOMAIN) is None


def test_a_gap_between_meshes_is_reported_with_its_size():
    problem = mesh_coverage_problem([[0, 0.6, 0, 1, 0, 3], [1.4, 2, 0, 1, 0, 3]], DOMAIN)
    assert "2.4 m3" in problem and "40.0%" in problem  # the audit's tiny.ifc case


def test_overlapping_meshes_are_reported():
    assert mesh_coverage_problem([[0, 1.3, 0, 1, 0, 3], [1.0, 2, 0, 1, 0, 3]], DOMAIN) == "MESH 1 and MESH 2 overlap"


def test_an_overlap_is_reported_even_when_volumes_add_up():
    # 0.3 m overlap between the first two boxes cancels a 0.3 m hole: the volumes sum to the domain volume
    problem = mesh_coverage_problem([[0, 1.3, 0, 1, 0, 3], [1.0, 1.7, 0, 1, 0, 3], [1.7, 2, 0, 1, 0, 3]], DOMAIN)
    assert "overlap" in problem


def test_rounding_of_a_shared_face_is_not_an_overlap():
    assert mesh_coverage_problem([[0, 1.00005, 0, 1, 0, 3], [1, 2, 0, 1, 0, 3]], DOMAIN) is None


@pytest.mark.parametrize("domain", [
    BoundingBox(xmin=0, xmax=40, ymin=0, ymax=30, zmin=0, zmax=12),
    BoundingBox(xmin=-3.7, xmax=61.3, ymin=2.2, ymax=47.9, zmin=-8.7, zmax=4.1),
])
def test_the_exporters_own_partition_always_tiles_its_domain(domain):
    meshes = partition_simulation_domain(domain, cell_size=0.2)
    assert len(meshes) > 1
    assert mesh_coverage_problem([xb for _, xb in meshes], domain.to_xb()) is None


def _audit_with_meshes(tmp_path, meshes):
    path = "tests/baseline/fixtures/tiny.ifc"
    base = convert([path], output_directory=tmp_path)
    text = re.sub(r"(?m)^&MESH .*? /$", meshes, base["fds_text"], count=1)
    assert text != base["fds_text"]
    manifest = MappingManifest.model_validate(base["manifest"])
    manifest.fds_sha256 = hashlib.sha256(text.encode()).hexdigest()
    manifest.reseal()
    _, _, report = audit([path], text, manifest, base["configuration"], base["geometry_package"])
    return report


def test_audit_rejects_a_deck_whose_meshes_leave_a_strip_of_the_domain_uncovered(tmp_path):
    report = _audit_with_meshes(tmp_path, "&MESH ID='M1', IJK=10,10,10, XB=0,0.6,0,1,0,3 /\n&MESH ID='M2', IJK=10,10,10, XB=1.4,2,0,1,0,3 /")
    assert report.gates["domain"].status == "FAIL"
    assert "without a computational mesh" in report.gates["domain"].reason
    assert report.mapping_status == "REJECTED"


def test_audit_accepts_two_meshes_that_tile_the_domain(tmp_path):
    report = _audit_with_meshes(tmp_path, "&MESH ID='M1', IJK=10,10,15, XB=0,1,0,1,0,3 /\n&MESH ID='M2', IJK=10,10,15, XB=1,2,0,1,0,3 /")
    assert report.gates["domain"].status == "PASS"
    assert report.mapping_status == "MAPPING_VERIFIED"
