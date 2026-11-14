"""inspect_mesh_quality is memoized per mesh bytes inside mesh_evidence_scope only."""

import pytest

from ifc_to_fds.core.canonical import BoundingBox
from ifc_to_fds.geometry import mesh as mesh_module


def cube():
    return mesh_module.box_mesh(BoundingBox(xmin=0, xmax=1, ymin=0, ymax=1, zmin=0, zmax=1))


@pytest.fixture
def calls(monkeypatch):
    counter = []
    real = mesh_module._compute_mesh_quality
    monkeypatch.setattr(
        mesh_module, "_compute_mesh_quality", lambda m: counter.append(1) or real(m)
    )
    return counter


def test_repeated_calls_inside_scope_compute_once(calls):
    mesh = cube()
    with mesh_module.mesh_evidence_scope():
        results = [mesh_module.inspect_mesh_quality(mesh) for _ in range(3)]
        assert mesh_module.valid_solid(mesh)
        # An equal copy has the same bytes and therefore the same key.
        assert mesh_module.inspect_mesh_quality(cube())["positive_volume"] == 1
    assert len(calls) == 1
    assert results[0] == results[1] == results[2]


def test_outside_scope_always_computes(calls):
    mesh = cube()
    for _ in range(3):
        mesh_module.inspect_mesh_quality(mesh)
    assert len(calls) == 3


def test_cache_returns_copies_and_edits_get_new_result(calls):
    mesh = cube()
    with mesh_module.mesh_evidence_scope():
        first = mesh_module.inspect_mesh_quality(mesh)
        first["positive_volume"] = 99  # callers cannot poison the cache
        assert mesh_module.inspect_mesh_quality(mesh)["positive_volume"] == 1
        mesh.vertices[0][0] -= 0.25  # edited vertex -> different key
        edited = mesh_module.inspect_mesh_quality(mesh)
        mesh.faces.pop()  # edited faces -> different key
        opened = mesh_module.inspect_mesh_quality(mesh)
    assert len(calls) == 3
    assert edited["is_closed_manifold"] == 1
    assert opened["open_edges"] > 0 and opened["is_closed_manifold"] == 0


def test_scope_does_not_leak_between_audits(calls):
    mesh = cube()
    with mesh_module.mesh_evidence_scope():
        mesh_module.inspect_mesh_quality(mesh)
    with mesh_module.mesh_evidence_scope():
        mesh_module.inspect_mesh_quality(mesh)
    assert len(calls) == 2
