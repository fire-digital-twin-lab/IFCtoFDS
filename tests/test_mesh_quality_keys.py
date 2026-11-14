"""inspect_mesh_quality counts edges with integer keys; results equal the np.unique(axis=0) definition."""

import numpy as np
import pytest
import trimesh

from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.geometry.mesh import inspect_mesh_quality


def _reference(mesh):
    verts = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    directed = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    _, occ = np.unique(directed, axis=0, return_counts=True)
    inconsistent = int(np.sum(occ - 1))
    _, occ = np.unique(np.sort(directed, axis=1), axis=0, return_counts=True)
    return inconsistent, int(np.count_nonzero(occ == 1)), int(np.count_nonzero(occ > 2))


def _meshes():
    box = trimesh.creation.box()
    yield TriangleMesh(vertices=box.vertices.tolist(), faces=box.faces.tolist())
    yield TriangleMesh(vertices=box.vertices.tolist(), faces=box.faces.tolist()[:-2])            # open
    yield TriangleMesh(vertices=box.vertices.tolist(), faces=[f[::-1] if k % 3 == 0 else f for k, f in enumerate(box.faces.tolist())])  # inconsistent
    yield TriangleMesh(vertices=box.vertices.tolist(), faces=box.faces.tolist() + box.faces.tolist()[:2])  # non-manifold (3 faces on an edge)
    sphere = trimesh.creation.icosphere(subdivisions=3)
    yield TriangleMesh(vertices=sphere.vertices.tolist(), faces=sphere.faces.tolist())
    rng = np.random.default_rng(3)
    yield TriangleMesh(vertices=rng.random((40, 3)).tolist(), faces=rng.integers(0, 40, (120, 3)).tolist())  # soup


@pytest.mark.parametrize("mesh", list(_meshes()))
def test_edge_counts_match_unique_definition(mesh):
    quality = inspect_mesh_quality(mesh)
    inconsistent, open_edges, non_manifold = _reference(mesh)
    assert (quality["inconsistent_edges"], quality["open_edges"], quality["non_manifold_edges"]) == (
        inconsistent, open_edges, non_manifold)
