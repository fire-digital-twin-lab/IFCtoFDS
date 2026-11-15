"""Rectilinear solids (walls with openings, L shapes) decompose exactly into axis-aligned boxes."""

import numpy as np
import pytest
import trimesh

from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.geometry.boolean import solid_boolean
from ifc_to_fds.geometry.mesh import as_trimesh
from ifc_to_fds.geometry.rectilinear import rectilinear_boxes


def _mesh(tm):
    return TriangleMesh(vertices=tm.vertices.tolist(), faces=tm.faces.tolist())


def _box(lo, hi):
    return trimesh.creation.box(bounds=[lo, hi])


def _volume_of(boxes):
    return sum((b[1] - b[0]) * (b[3] - b[2]) * (b[5] - b[4]) for b in boxes)


def test_single_box_is_one_box():
    assert rectilinear_boxes(_mesh(_box((0, 0, 0), (2, 0.2, 3)))) == [(0, 2, 0, 0.2, 0, 3)]


def test_wall_with_a_window_hole_is_covered_exactly():
    wall = _box((0, 0, 0), (4, 0.2, 3))
    hole = _box((1, -0.1, 1), (2, 0.3, 2))
    solid = solid_boolean([wall, hole], "difference")
    boxes = rectilinear_boxes(_mesh(solid))
    assert boxes and len(boxes) <= 8
    assert _volume_of(boxes) == pytest.approx(solid.volume, abs=1e-9)
    # no box overlaps the hole
    assert all(not (b[0] < 2 and b[1] > 1 and b[4] < 2 and b[5] > 1) for b in boxes)


def test_l_shape_and_cavity():
    l_shape = solid_boolean([_box((0, 0, 0), (2, 1, 1)), _box((0, 0, 0), (1, 1, 2))], "union")
    boxes = rectilinear_boxes(_mesh(l_shape))
    assert boxes and _volume_of(boxes) == pytest.approx(l_shape.volume, abs=1e-9)
    # An inner cavity is a second shell; a box cover would change the shell count, so it is refused.
    cavity = solid_boolean([_box((0, 0, 0), (3, 3, 3)), _box((1, 1, 1), (2, 2, 2))], "difference")
    assert rectilinear_boxes(_mesh(cavity)) is None


def test_non_rectilinear_and_oversized_inputs_return_none():
    assert rectilinear_boxes(_mesh(trimesh.creation.icosphere(subdivisions=1))) is None
    wedge = trimesh.creation.box()
    wedge.vertices[wedge.vertices[:, 2] > 0, 0] += 0.3  # slanted faces
    assert rectilinear_boxes(_mesh(wedge)) is None
    assert rectilinear_boxes(_mesh(_box((0, 0, 0), (1, 1, 1))), max_cells=0) is None


def test_boxes_union_equals_the_source_solid():
    solid = solid_boolean([_box((0, 0, 0), (4, 0.2, 3)), _box((1, -0.1, 0), (2, 0.3, 2.1))], "difference")
    boxes = rectilinear_boxes(_mesh(solid))
    union = solid_boolean([_box((b[0], b[2], b[4]), (b[1], b[3], b[5])) for b in boxes], "union")
    assert union.volume == pytest.approx(solid.volume, abs=1e-9)
    assert np.allclose(union.bounds, solid.bounds)


def test_several_touching_components_are_not_merged_into_one_box_cover():
    """Frame + glass style bodies keep their identity: their box cover would change shells and area."""
    two = trimesh.util.concatenate([_box((0, 0, 0), (1, 1, 1)), _box((1, 0, 0), (2, 1, 1))])
    assert rectilinear_boxes(_mesh(two)) is None
