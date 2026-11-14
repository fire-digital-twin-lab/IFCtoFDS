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
