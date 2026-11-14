"""The faster winding-number oracle gives the same numbers as the original vectorised-by-broadcast version."""

import numpy as np
import trimesh

from ifc_to_fds.geometry.component_union import winding_numbers


def reference(tm, points, chunk=128):
    """The original implementation (plan M1.7 profile: 196 of 252 s of the independent re-read)."""
    triangles = tm.triangles
    result = np.empty(len(points))
    for start in range(0, len(points), chunk):
        p = points[start : start + chunk, None, None, :]
        a, b, c = (triangles[None, :, k, :] - p[:, :, 0, :] for k in range(3))
        la, lb, lc = (np.linalg.norm(v, axis=-1) for v in (a, b, c))
        numerator = np.einsum("pfk,pfk->pf", a, np.cross(b, c))
        denominator = (
            la * lb * lc
            + np.einsum("pfk,pfk->pf", a, b) * lc
            + np.einsum("pfk,pfk->pf", a, c) * lb
            + np.einsum("pfk,pfk->pf", b, c) * la
        )
        result[start : start + chunk] = (2.0 * np.arctan2(numerator, denominator)).sum(axis=1) / (4 * np.pi)
    return result


def test_matches_the_original_on_curved_and_boxy_meshes():
    rng = np.random.default_rng(7)
    meshes = [
        trimesh.creation.box(extents=(1, 2, 3)),
        trimesh.creation.icosphere(subdivisions=3, radius=1.5),
        trimesh.creation.cylinder(radius=0.4, height=2.0, sections=48),
        trimesh.util.concatenate([trimesh.creation.box(), trimesh.creation.box().apply_translation((0.5, 0.2, 0.1))]),
    ]
    for tm in meshes:
        points = rng.uniform(-3, 3, (300, 3))
        on_surface = tm.vertices[:20]  # points exactly on the surface
        points[: len(on_surface)] = on_surface
        assert np.allclose(winding_numbers(tm, points), reference(tm, points), atol=1e-9, equal_nan=True)


def test_inside_outside_decision_is_unchanged():
    tm = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    points = np.random.default_rng(1).uniform(-1.5, 1.5, (500, 3))
    assert np.array_equal(winding_numbers(tm, points) > 0.5, reference(tm, points) > 0.5)


def test_empty_point_set_and_single_point():
    tm = trimesh.creation.box()
    assert winding_numbers(tm, np.empty((0, 3))).shape == (0,)
    assert winding_numbers(tm, np.zeros((1, 3)))[0] > 0.9
