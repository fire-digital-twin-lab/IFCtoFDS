"""Rebase must move storey elevations with the geometry, and trigger on large Z."""

from pathlib import Path

import pytest

from ifc_to_fds.core.federation import load_sources

TINY = str(Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc")


def test_explicit_rebase_vector_shifts_storey_elevation_with_mesh():
    base = load_sources([TINY], {"auto_rebase_origin": False})
    shifted = load_sources([TINY], {"rebase_vector": [1001.0, 0.0, 3.0]})
    assert shifted.model_bounds.zmin == pytest.approx(base.model_bounds.zmin - 3.0)
    before = {s.storey_id: s.elevation_m for s in base.storey_references}
    after = {s.storey_id: s.elevation_m for s in shifted.storey_references}
    assert before and before.keys() == after.keys()
    for key in before:
        assert after[key] == pytest.approx(before[key] - 3.0)


def test_unknown_storey_elevation_stays_unknown():
    base = load_sources([TINY], {"auto_rebase_origin": False})
    for s in base.storey_references:
        s.elevation_m = None
    from ifc_to_fds.core.federation import rebase_model_to_origin

    rebase_model_to_origin(base, rebase_vector=[0.0, 0.0, 5.0])
    assert all(s.elevation_m is None for s in base.storey_references)


def test_auto_rebase_triggers_on_large_z_only():
    from ifc_to_fds.core.federation import rebase_model_to_origin

    model = load_sources([TINY], {"auto_rebase_origin": False})
    for e in (e for e in model.elements if e.mesh):  # lift the whole model 2000 m in Z, nothing in X/Y
        e.mesh.vertices = [[v[0], v[1], v[2] + 2000.0] for v in e.mesh.vertices]
        e.bounding_box.zmin += 2000.0
        e.bounding_box.zmax += 2000.0
    model.model_bounds.zmin += 2000.0
    model.model_bounds.zmax += 2000.0
    _, shift = rebase_model_to_origin(model, auto_rebase=True)
    assert shift == (0.0, 0.0, 2000.0)
    assert model.model_bounds.zmin == pytest.approx(0.0)
