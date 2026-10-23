import numpy as np
import pytest

from ifc_to_fds.geometry.mesh import inspect_mesh_quality, as_trimesh, box_mesh
from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.validation.metrics import (
    SolidCandidateIndex,
    passage_metrics,
    compare_solids,
)


def legacy_quality(mesh):
    """Independent pre-optimization algorithm retained only as a parity oracle."""
    verts = np.asarray(mesh.vertices)
    edges, directed = {}, set()
    degenerate = invalid = inconsistent = 0
    for face in mesh.faces:
        if len(face) != 3 or any(i < 0 or i >= len(verts) for i in face):
            invalid += 1
            continue
        a, b, c = face
        degenerate += int(
            len(set(face)) != 3
            or np.linalg.norm(np.cross(verts[b] - verts[a], verts[c] - verts[a]))
            < 1e-12
        )
        for x, y in ((a, b), (b, c), (c, a)):
            edge = tuple(sorted((x, y)))
            edges[edge] = edges.get(edge, 0) + 1
            inconsistent += int((x, y) in directed)
            directed.add((x, y))
    opened, nonmanifold = (
        sum(n == 1 for n in edges.values()),
        sum(n > 2 for n in edges.values()),
    )
    closed = int(
        bool(mesh.faces)
        and not any((degenerate, invalid, inconsistent, opened, nonmanifold))
    )
    return dict(
        degenerate_faces=degenerate,
        invalid_indices=invalid,
        open_edges=opened,
        non_manifold_edges=nonmanifold,
        inconsistent_edges=inconsistent,
        is_closed_manifold=closed,
        positive_volume=int(closed and as_trimesh(mesh).volume > 1e-12),
        finite=1,
    )


@pytest.mark.parametrize(
    "mutation", ["clean", "hole", "reverse", "duplicate", "index", "degenerate", "all"]
)
def test_vectorized_quality_preserves_defect_counts(box_model, mutation):
    mesh = box_model.elements[0].mesh
    if mutation in ("hole", "all"):
        mesh.faces.pop()
    if mutation in ("reverse", "all"):
        mesh.faces[0].reverse()
    if mutation in ("duplicate", "all"):
        mesh.faces.append(mesh.faces[1][:])
    if mutation in ("index", "all"):
        mesh.faces += [[0, 1, 10**30], [-1, 0, 1], [0, 1]]
    if mutation in ("degenerate", "all"):
        mesh.faces += [[0, 0, 1]]
    assert inspect_mesh_quality(mesh) == legacy_quality(mesh)


def test_spatial_candidates_preserve_free_volume_and_blockers(box_model):
    opening = box_model.elements[0].mesh
    blocker = box_mesh(BoundingBox(xmin=0.2, xmax=0.4, ymin=0, ymax=1, zmin=0, zmax=3))
    distant = box_mesh(BoundingBox(xmin=20, xmax=22, ymin=0, ymax=1, zmin=0, zmax=3))
    source, output = [distant], [blocker, distant]
    direct = passage_metrics(source, output, opening)
    indexed = passage_metrics(
        SolidCandidateIndex(source), SolidCandidateIndex(output), opening
    )
    assert indexed == direct
    assert indexed["normalized_symmetric_difference"] > 0


def test_exact_geometry_proof_avoids_boolean_without_skipping_topology(
    box_model, monkeypatch
):
    from ifc_to_fds.validation import metrics

    mesh = box_model.elements[0].mesh

    def unavailable(*args, **kwargs):
        raise RuntimeError("Boolean unavailable")

    monkeypatch.setattr(metrics, "solid_boolean", unavailable)
    assert (
        compare_solids(mesh, [mesh.model_copy(deep=True)])["comparison_method"]
        == "EXACT_ORIENTED_TRIANGLES"
    )
    broken = mesh.model_copy(deep=True)
    broken.faces.pop()
    with pytest.raises(ValueError, match="invalid solids"):
        compare_solids(broken, [broken])


def test_binary64_boolean_preserves_thin_intersection_at_world_origin():
    from ifc_to_fds.geometry.boolean import solid_boolean

    origin = 123.1234567890123
    bounds = BoundingBox(
        xmin=origin, xmax=origin + 0.000012, ymin=0, ymax=1, zmin=0, zmax=3
    )
    shifted = bounds.model_copy(
        update={"xmin": origin + 0.000002, "xmax": origin + 0.000014}
    )
    source, output = box_mesh(bounds), box_mesh(shifted)
    intersection = solid_boolean(
        [as_trimesh(source), as_trimesh(output)], "intersection"
    )
    assert intersection.volume == pytest.approx(
        (bounds.xmax - shifted.xmin) * 3, rel=1e-8
    )
    measured = compare_solids(source, [output])
    assert measured["solid_iou"] < 0.8
