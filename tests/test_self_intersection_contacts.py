"""Face contact between solids is not a self-intersection; real overlap still is."""

import numpy as np
import pytest
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


def test_coplanar_prefilter_changes_no_evidence(monkeypatch):
    """The separating-axis prefilter only skips pairs that cannot overlap; evidence is identical."""
    import numpy as np

    from ifc_to_fds.geometry import mesh as mesh_module

    rng = np.random.default_rng(7)
    cases = [
        _boxes(((0, 0, 0), (1, 1, 1)), ((1, 0, 0), (2, 1, 1))),
        _boxes(((0, 0, 0), (1, 1, 1)), ((1, 0.5, 0), (2, 1.5, 1)), ((0, 1, 0), (1, 2, 1))),
        _boxes(((0, 0, 0), (2, 2, 2)), ((0.5, 0.5, 1), (1, 1, 2))),
        _boxes(((0, 0, 0), (1, 1, 1)), ((0.2, 0.2, 0.5), (0.8, 0.8, 1))),
        _two_triangles(1e-7),
    ]
    for _ in range(12):
        lo = rng.integers(0, 3, 3).astype(float)
        cases.append(_boxes((tuple(lo), tuple(lo + 1)), (tuple(lo + rng.integers(-1, 2, 3)), tuple(lo + rng.integers(-1, 2, 3) + 2))))
    for mesh in cases:
        monkeypatch.setattr(mesh_module, "COPLANAR_PREFILTER", False)
        plain = self_intersection_evidence(mesh)
        monkeypatch.setattr(mesh_module, "COPLANAR_PREFILTER", True)
        assert self_intersection_evidence(mesh) == plain


def test_coplanar_prefilter_skips_touching_pairs(monkeypatch):
    """Touching faces never reach the per-pair polygon intersection."""
    import shapely.geometry

    calls = []
    real = shapely.geometry.Polygon
    monkeypatch.setattr(shapely.geometry, "Polygon", lambda *a, **k: calls.append(1) or real(*a, **k))
    strip = _boxes(*[((k, 0, 0), (k + 1, 1, 1)) for k in range(4)])  # four boxes in a row, faces touching
    evidence = self_intersection_evidence(strip)
    assert evidence["status"] == "CLEAN" and evidence["contact"]["face_pairs"] > 0
    assert len(calls) <= 2 * evidence["contact"]["face_pairs"]  # only genuinely overlapping pairs


def _poke(depth):
    """A small triangle standing on a big one, its tip `depth` metres below the big triangle's plane.

    The big triangle spans both sides of the small one's plane, so only the small
    triangle's reach through the big one is the material overlap.
    """
    return TriangleMesh(
        vertices=[[0, 0, 0], [4, 0, 0], [0, 4, 0], [1, 1, 1.0], [1.5, 1, 1.0], [1.25, 1.0, -depth]],
        faces=[[0, 1, 2], [3, 4, 5]],
    )


def test_tip_poking_through_by_less_than_cad_precision_is_numerical_contact():
    for depth in (1e-14, 1e-12, 1e-8, 5e-6):
        evidence = self_intersection_evidence(_poke(depth))
        assert evidence["status"] == "CLEAN" and evidence["numerical_contact"]["face_pairs"] == 1, depth


def test_tip_poking_through_by_more_than_cad_precision_is_confirmed():
    for depth in (1e-4, 0.01, 0.5):
        assert self_intersection_evidence(_poke(depth))["status"] == "CONFIRMED", depth


def test_vectorised_penetration_depth_matches_scalar_definition():
    import numpy as np

    from ifc_to_fds.geometry.mesh import _penetration_depths

    rng = np.random.default_rng(11)
    a = rng.normal(size=(300, 3, 3))
    b = rng.normal(size=(300, 3, 3))
    b[:50] = a[:50] + rng.normal(scale=1e-9, size=(50, 3, 3))  # near-coplanar pairs
    got = _penetration_depths(a, b)
    for k in range(len(a)):
        n = np.cross(a[k][1] - a[k][0], a[k][2] - a[k][0])
        d = (b[k] - a[k][0]) @ (n / np.linalg.norm(n))
        want = min(d.max(), -d.min()) if d.max() > 0 > d.min() else 0.0
        assert got[k] == pytest.approx(want, abs=1e-15)
    assert (_penetration_depths(a[:1] * 0, b[:1]) == 0).all()  # degenerate triangle: no depth, no crash
