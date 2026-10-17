import pytest
from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.geometry.mesh import has_self_intersection


def test_close_parallel_sloping_triangles_are_not_coplanar():
    # Analytic planes z=x+y and z=x+y+2**-42 never intersect.
    # Their AABBs overlap: this reproduced the old distance-epsilon false FAIL.
    gap = 2 ** -42
    mesh = TriangleMesh(
        vertices=[[0,0,0],[1,0,1],[0,1,1],[0,0,gap],[1,0,1+gap],[0,1,1+gap]],
        faces=[[0,1,2],[3,4,5]],
    )
    assert not has_self_intersection(mesh)


def test_coplanar_overlap_is_confirmed():
    mesh = TriangleMesh(vertices=[[0,0,0],[1,0,1],[0,1,1]] * 2, faces=[[0,1,2],[3,4,5]])
    assert has_self_intersection(mesh)


def test_intersection_backend_failure_is_uncertain(monkeypatch, box_model):
    from ifc_to_fds.validation.metrics import compare_solids
    import trimesh

    def unavailable(*args, **kwargs):
        raise RuntimeError("intersection predicate unavailable")

    monkeypatch.setattr(trimesh.Trimesh, "triangles_tree", property(unavailable))
    with pytest.raises(RuntimeError, match="unavailable"):
        compare_solids(box_model.elements[0].mesh, [box_model.elements[0].mesh])
