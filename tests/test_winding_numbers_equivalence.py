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


def test_threaded_blocks_give_the_single_thread_result(monkeypatch):
    """The small test meshes never reach the thread pool, so force it on a mesh large enough to split."""
    import ifc_to_fds.geometry.component_union as union

    tm = trimesh.creation.icosphere(subdivisions=4, radius=1.0)  # 5,120 triangles
    points = np.random.default_rng(11).uniform(-1.4, 1.4, (257, 3))  # an odd count: a short last block
    monkeypatch.setattr(union, "_WORKERS", 1)
    single = winding_numbers(tm, points)
    monkeypatch.setattr(union, "_WORKERS", 4)
    monkeypatch.setattr(union, "_pool", None)
    monkeypatch.setattr(union, "THREADED_PAIRS", 0)
    monkeypatch.setattr(union, "PAIRS_PER_CHUNK", 1 << 12)  # several blocks so the pool really splits the work
    threaded = winding_numbers(tm, points)
    assert np.array_equal(single, threaded)
    assert np.allclose(threaded, reference(tm, points), atol=1e-9)


def test_inside_skips_only_points_that_cannot_be_inside():
    """_inside must agree with the plain winding test, also next to the bounding box and for a point on a face."""
    from ifc_to_fds.geometry.component_union import _inside

    tm = trimesh.creation.box(extents=(2, 2, 2))
    low, high = tm.bounds
    points = np.array([
        [0, 0, 0],                       # inside
        [0.9, 0.9, 0.9],                 # inside, close to a corner
        [high[0] + 1e-10, 0, 0],         # outside, within the margin of the box
        [high[0] + 1e-6, 0, 0],          # outside the margin
        [high[0], 0, 0],                 # on a face
        [low[0] - 5, low[1] - 5, 0],     # far away
    ])
    assert np.array_equal(_inside(tm, points), winding_numbers(tm, points) > 0.5)
    assert list(_inside(tm, points[:4])) == [True, True, False, False]
