"""Overlapping sub-solids of one IFC product are fused into the region they occupy."""

import trimesh

from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.geometry.component_union import fuse_overlapping_components
from ifc_to_fds.geometry.engine import prepare_source_mesh
from ifc_to_fds.geometry.mesh import as_trimesh, self_intersection_evidence, valid_solid


def _boxes(*specs):
    vertices, faces = [], []
    for lo, hi in specs:
        b = trimesh.creation.box(bounds=[lo, hi])
        faces += (b.faces + len(vertices)).tolist()
        vertices += b.vertices.tolist()
    return TriangleMesh(vertices=vertices, faces=faces)


def test_overlapping_components_are_fused_and_proven():
    mesh = _boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0.25, 0.25), (1.5, 0.75, 0.75)))  # frame + pane style overlap
    assert self_intersection_evidence(mesh)["status"] == "CONFIRMED"
    fused, proof = fuse_overlapping_components(mesh)
    assert proof["status"] == "APPLIED"
    assert proof["components"] == 2
    assert valid_solid(fused) and self_intersection_evidence(fused)["status"] == "CLEAN"
    assert abs(as_trimesh(fused).volume - (1.0 + 0.25 - 0.125)) < 1e-9
    assert proof["oracle"]["mismatches"] == 0 and proof["oracle"]["samples"] >= 1000
    assert len(as_trimesh(fused).split(only_watertight=False, repair=False)) == 1


def test_clean_meshes_are_returned_unchanged():
    single = _boxes(((0, 0, 0), (1, 1, 1)))
    assert fuse_overlapping_components(single) == (single, None)
    separate = _boxes(((0, 0, 0), (1, 1, 1)), ((2, 0, 0), (3, 1, 1)))
    assert fuse_overlapping_components(separate) == (separate, None)
    touching = _boxes(((0, 0, 0), (1, 1, 1)), ((1, 0, 0), (2, 1, 1)))  # contact, not overlap
    assert fuse_overlapping_components(touching) == (touching, None)


def test_nested_component_is_absorbed():
    mesh = _boxes(((0, 0, 0), (2, 2, 2)), ((0.5, 0.5, 0.5), (1, 1, 1)))
    fused, proof = fuse_overlapping_components(mesh)
    assert proof["status"] == "APPLIED"
    assert abs(as_trimesh(fused).volume - 8.0) < 1e-9


def test_prepare_source_mesh_records_the_union():
    mesh, diagnostics = prepare_source_mesh(_boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0, 0), (1.5, 1, 1))))
    assert diagnostics["component_union"]["status"] == "APPLIED"
    assert self_intersection_evidence(mesh)["status"] == "CLEAN"
    _, plain = prepare_source_mesh(_boxes(((0, 0, 0), (1, 1, 1))))
    assert "component_union" not in plain


def test_winding_number_inside_outside_and_overlap():
    import numpy as np

    from ifc_to_fds.geometry.component_union import winding_numbers

    mesh = as_trimesh(_boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0.5, 0.5), (1.5, 1.5, 1.5))))
    w = winding_numbers(mesh, np.array([[0.25, 0.25, 0.25], [0.75, 0.75, 0.75], [3.0, 3.0, 3.0]]))
    assert abs(w[0] - 1) < 1e-9 and abs(w[1] - 2) < 1e-9 and abs(w[2]) < 1e-9


def test_fusion_is_deterministic():
    from ifc_to_fds.geometry.mesh import mesh_digest

    mesh = _boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0.25, 0.25), (1.5, 0.75, 0.75)))
    first, a = fuse_overlapping_components(mesh)
    second, b = fuse_overlapping_components(mesh.model_copy(deep=True))
    assert mesh_digest(first) == mesh_digest(second) and a == b


def test_nothing_to_fuse_never_runs_a_self_intersection_scan(monkeypatch):
    """Deciding that no component overlaps another must not scan every triangle pair of the mesh."""
    from ifc_to_fds.geometry import component_union

    def forbidden(mesh):
        raise AssertionError("self-intersection scan on the unfused mesh")

    monkeypatch.setattr(component_union, "self_intersection_evidence", forbidden)
    touching = _boxes(((0, 0, 0), (1, 1, 1)), ((1, 0, 0), (2, 1, 1)))
    assert component_union.fuse_overlapping_components(touching) == (touching, None)
    # An overlap is detected from volumes alone; only the fused result is then proven clean.
    monkeypatch.undo()
    overlapping = _boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0.25, 0.25), (1.5, 0.75, 0.75)))
    assert component_union.fuse_overlapping_components(overlapping)[1]["status"] == "APPLIED"


def test_overlap_volume_is_reported():
    mesh = _boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0.25, 0.25), (1.5, 0.75, 0.75)))
    _, proof = fuse_overlapping_components(mesh)
    assert abs(proof["overlap_volume_m3"] - 0.125) < 1e-9


def test_fusing_does_not_scan_its_own_result(monkeypatch):
    """The fused mesh is proven by volumes and the winding oracle; the audit's preflight scans it once."""
    from ifc_to_fds.geometry import component_union

    scans = []
    real = component_union.self_intersection_evidence
    monkeypatch.setattr(component_union, "self_intersection_evidence", lambda m: scans.append(1) or real(m))
    mesh = _boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0.25, 0.25), (1.5, 0.75, 0.75)))
    fused, proof = component_union.fuse_overlapping_components(mesh)
    assert proof["status"] == "APPLIED" and not scans
    assert self_intersection_evidence(fused)["status"] == "CLEAN"  # what the audit does next


def test_union_that_a_scan_would_reject_is_still_caught_by_the_audit():
    """A refused or defective fuse leaves a mesh the preflight blocks; nothing is silently accepted."""
    from ifc_to_fds.geometry.component_union import fuse_overlapping_components as fuse

    bad = TriangleMesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]])  # not a solid
    assert fuse(bad) == (bad, None)
