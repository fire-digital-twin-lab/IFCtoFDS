"""Comparing a set of obstacles with itself must report no passage change."""

from pathlib import Path

import pytest

from ifc_to_fds.application.services.model_preparer import prepare_model
from ifc_to_fds.mapping.boundary import target_mesh
from ifc_to_fds.validation.metrics import SolidCandidateIndex, passage_metrics

FZK = Path(__file__).resolve().parents[1] / "examples" / "AC20-FZK-Haus.ifc"
# Openings where Manifold intersection of a free volume with itself lost 1.8-5.4% volume.
OPENING_STEPS = (22174, 31539, 31607)


@pytest.fixture(scope="module")
def fzk():
    model = prepare_model([str(FZK)], {}, reference=True)
    meshes = [
        target_mesh(e)
        for e in model.elements
        if e.mesh
        and e.role == "PHYSICAL"
        and e.mapping_strategy.value in ("OBST", "GEOM")
        and e.scope_decision.value in ("IN_SCOPE", "BOUNDARY_RETAINED")
    ]
    return model, meshes


@pytest.mark.parametrize("step", OPENING_STEPS)
def test_same_index_on_both_sides_has_zero_difference(fzk, step):
    model, meshes = fzk
    opening = next(o for h in model.elements for o in h.openings if o.opening_step_id == step)
    one = SolidCandidateIndex(meshes)
    result = passage_metrics(one, one, opening.mesh)
    assert result["normalized_symmetric_difference"] == 0.0
    assert result["source_free_components"] == result["output_free_components"]


@pytest.mark.parametrize("step", OPENING_STEPS)
def test_equal_but_separate_indexes_have_zero_difference(fzk, step):
    model, meshes = fzk
    opening = next(o for h in model.elements for o in h.openings if o.opening_step_id == step)
    result = passage_metrics(SolidCandidateIndex(meshes), SolidCandidateIndex(list(meshes)), opening.mesh)
    assert result["normalized_symmetric_difference"] == 0.0


def test_same_obstacles_with_different_triangulation_have_zero_difference():
    """An OBST rebuilt from XB and the source box differ in triangles, not in space."""
    import trimesh

    from ifc_to_fds.domain.bim import TriangleMesh

    def mesh(tm):
        return TriangleMesh(vertices=tm.vertices.tolist(), faces=tm.faces.tolist())

    wall = trimesh.creation.box(bounds=[[0, 0, 0], [4, 0.2, 3]])
    left_jamb = trimesh.creation.box(bounds=[[0.9, -0.1, 0], [1.0, 0.3, 2.1]])
    source = [mesh(wall.subdivide()), mesh(left_jamb.subdivide().subdivide())]
    exported = [mesh(left_jamb), mesh(wall)]  # other order and triangulation
    opening = mesh(trimesh.creation.box(bounds=[[0.8, -0.05, 0], [1.8, 0.25, 2.1]]))
    result = passage_metrics(source, exported, opening)
    assert result["normalized_symmetric_difference"] == 0.0
    assert result["source_free_components"] == result["output_free_components"]


def test_changed_obstacle_is_still_measured():
    import trimesh

    from ifc_to_fds.domain.bim import TriangleMesh

    def mesh(tm):
        return TriangleMesh(vertices=tm.vertices.tolist(), faces=tm.faces.tolist())

    opening = mesh(trimesh.creation.box(bounds=[[0.8, -0.05, 0], [1.8, 0.25, 2.1]]))
    blocker = mesh(trimesh.creation.box(bounds=[[1.0, -0.1, 0], [1.6, 0.3, 2.1]]))
    result = passage_metrics([], [blocker], opening)
    assert result["normalized_symmetric_difference"] > 0.5
