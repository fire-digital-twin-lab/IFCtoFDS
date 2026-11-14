"""Heavy meshes are scanned in worker processes; results equal the sequential ones."""

import numpy as np
import trimesh

from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.geometry import mesh as mesh_module
from ifc_to_fds.geometry.mesh import (
    mesh_evidence_scope,
    prefetch_self_intersection,
    self_intersection_evidence,
)


def _boxes(*specs):
    vertices, faces = [], []
    for lo, hi in specs:
        b = trimesh.creation.box(bounds=[lo, hi])
        faces += (b.faces + len(vertices)).tolist()
        vertices += b.vertices.tolist()
    return TriangleMesh(vertices=vertices, faces=faces)


def _meshes():
    return [
        _boxes(((0, 0, 0), (1, 1, 1)), ((1, 0, 0), (2, 1, 1))),                 # contact -> CLEAN
        _boxes(((0, 0, 0), (1, 1, 1)), ((0.5, 0.25, 0.25), (1.5, 0.75, 0.75))),   # overlap -> CONFIRMED
        _boxes(((0, 0, 0), (2, 2, 2)), ((0.5, 0.5, 0.5), (1, 1, 1))),             # nested -> CONFIRMED
    ]


def test_prefetched_evidence_equals_sequential_and_is_cached(monkeypatch):
    meshes = _meshes()
    expected = [self_intersection_evidence(m) for m in meshes]
    with mesh_evidence_scope():
        prefetch_self_intersection(meshes, min_faces=0)
        calls = []
        real = mesh_module.has_self_intersection
        monkeypatch.setattr(mesh_module, "has_self_intersection", lambda m: calls.append(1) or real(m))
        got = [self_intersection_evidence(m) for m in meshes]
    assert got == expected
    assert not calls  # served from the prefetched cache, nothing recomputed in this process


def test_prefetch_is_a_no_op_outside_an_evidence_scope_and_for_light_meshes():
    prefetch_self_intersection(_meshes(), min_faces=0)  # no scope: must not raise or leak state
    with mesh_evidence_scope():
        prefetch_self_intersection(_meshes(), min_faces=10**6)  # all below the size threshold
        assert not mesh_module._intersection_evidence.get()
