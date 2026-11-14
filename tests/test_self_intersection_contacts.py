"""Face contact between solids is not a self-intersection; real overlap still is."""

import numpy as np
import trimesh

from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.geometry.mesh import has_self_intersection, self_intersection_evidence


def _boxes(*specs):
    vertices, faces = [], []
    for lo, hi in specs:
        b = trimesh.creation.box(bounds=[lo, hi])
        faces += (b.faces + len(vertices)).tolist()
        vertices += b.vertices.tolist()
    return TriangleMesh(vertices=vertices, faces=faces)


def test_boxes_sharing_a_face_are_contact_not_intersection():
    mesh = _boxes(((0, 0, 0), (1, 1, 1)), ((1, 0, 0), (2, 1, 1)))
    details = {}
    assert has_self_intersection(mesh, details)  # strict predicate keeps its old contract
    assert details["kind"] == "COPLANAR_FACE_OVERLAP"
    evidence = self_intersection_evidence(mesh)
    assert evidence["status"] == "CLEAN"
    assert evidence["contact"]["face_pairs"] > 0
    assert abs(evidence["contact"]["area_m2"] - 1.0) < 1e-9


def test_separated_boxes_have_no_contact_record():
    evidence = self_intersection_evidence(_boxes(((0, 0, 0), (1, 1, 1)), ((1.000001, 0, 0), (2, 1, 1))))
    assert evidence["status"] == "CLEAN" and "contact" not in evidence


def test_volume_overlap_and_nesting_stay_confirmed():
    assert self_intersection_evidence(_boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0, 0), (1.5, 1, 1))))["status"] == "CONFIRMED"
    assert self_intersection_evidence(_boxes(((0, 0, 0), (2, 2, 2)), ((0.5, 0.5, 0.5), (1, 1, 1))))["status"] == "CONFIRMED"
    # Same-facing coplanar tops over a real overlap: material on the same side.
    assert self_intersection_evidence(_boxes(((0, 0, 0), (1, 1, 1)), ((0.2, 0.2, 0.5), (0.8, 0.8, 1))))["status"] == "CONFIRMED"


def test_same_facing_overlap_below_cad_precision_is_numerical_contact():
    eps = 1e-6  # overlap area eps^2/2 = 5e-13 m^2, below the 1e-10 m^2 (1e-5 m)^2 floor
    mesh = TriangleMesh(
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [1 - eps, 0, 0], [2, 0, 0], [1 - eps, 1, 0]],
        faces=[[0, 1, 2], [3, 4, 5]],
    )
    assert has_self_intersection(mesh, {})
    evidence = self_intersection_evidence(mesh)
    assert evidence["status"] == "CLEAN"
    assert evidence["numerical_contact"]["face_pairs"] == 1
    big = TriangleMesh(vertices=mesh.vertices[:3] + [[0.9, 0, 0], [2, 0, 0], [0.9, 1, 0]], faces=mesh.faces)
    assert self_intersection_evidence(big)["status"] == "CONFIRMED"


def _two_triangles(depth):
    """T2 pierces the interior of T1 (plane z=0) by `depth` on each side."""
    return TriangleMesh(
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0.3, 0.3, -depth], [0.6, 0.3, depth], [0.3, 0.6, depth]],
        faces=[[0, 1, 2], [3, 4, 5]],
    )


def test_crossing_shallower_than_cad_precision_is_numerical_contact():
    shallow = _two_triangles(1e-7)
    assert has_self_intersection(shallow, {})
    evidence = self_intersection_evidence(shallow)
    assert evidence["status"] == "CLEAN"
    assert evidence["numerical_contact"]["face_pairs"] == 1


def test_deep_crossing_stays_a_witness():
    evidence = self_intersection_evidence(_two_triangles(0.1))
    assert evidence["status"] == "CONFIRMED"
    assert evidence["witness"]["kind"] == "TRIANGLE_CROSSING"
    assert self_intersection_evidence(_two_triangles(1e-4))["status"] == "CONFIRMED"
