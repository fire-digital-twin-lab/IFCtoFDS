"""Two triangulations of the same planar surfaces are the same surface; a real shift is not."""

import trimesh

from ifc_to_fds.geometry.boolean import solid_boolean
from ifc_to_fds.validation.metrics import same_surface_partition


def _wall_with_door():
    wall = trimesh.creation.box(bounds=[(0, 0, 0), (4, 0.3, 3)])
    return solid_boolean([wall, trimesh.creation.box(bounds=[(-0.1, -0.1, -0.1), (1, 0.4, 2.1)])], "difference")


def _two_boxes():
    return solid_boolean([trimesh.creation.box(bounds=[(0, 0, 2.1), (4, 0.3, 3)]),
                          trimesh.creation.box(bounds=[(1, 0, 0), (4, 0.3, 2.1)])], "union")


def test_same_surface_with_a_different_triangulation_is_proven():
    a, b = _wall_with_door(), _two_boxes()
    assert len(a.faces) != len(b.faces)
    assert same_surface_partition(a, b)


def test_a_micron_shift_of_one_plane_is_not_the_same_surface():
    a = _wall_with_door()
    b = solid_boolean([trimesh.creation.box(bounds=[(0, 0, 2.1), (4, 0.3, 3)]),
                       trimesh.creation.box(bounds=[(1 + 1e-6, 0, 0), (4, 0.3, 2.1)])], "union")
    assert not same_surface_partition(a, b)


def test_ulp_noise_in_the_coordinates_does_not_break_the_proof():
    import numpy as np

    a, b = _wall_with_door(), _two_boxes()
    rng = np.random.default_rng(5)
    noisy = trimesh.Trimesh(b.vertices + rng.normal(scale=1e-15, size=b.vertices.shape), b.faces, process=False)
    assert same_surface_partition(a, noisy)
