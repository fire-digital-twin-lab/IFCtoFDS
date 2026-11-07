"""Scientific regressions for the exact triangle/AABB clearance oracle."""

import math

import pytest
import trimesh

from ifc_to_fds.domain.bim import BoundingBox, TriangleMesh
from ifc_to_fds.geometry.triangle_box import (
    outward_expanded_bounds,
    prove_mesh_clearance_from_box,
    triangle_overlaps_aabb_exact,
)


def _tetrahedron(vertices):
    # Consistent outward winding for a tetrahedron whose fourth vertex is the
    # positive x/y/z corner.
    return TriangleMesh(
        vertices=[list(point) for point in vertices],
        faces=[[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]],
    )


def _box(extents, translation):
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(translation)
    return TriangleMesh(vertices=mesh.vertices.tolist(), faces=mesh.faces.tolist())


def test_exact_sat_counts_boundary_contact_as_overlap():
    bounds = BoundingBox(xmin=0, xmax=1, ymin=0, ymax=1, zmin=0, zmax=1)
    touching = [[1.0, 0.2, 0.2], [1.0, 0.8, 0.2], [1.0, 0.2, 0.8]]
    assert triangle_overlaps_aabb_exact(touching, bounds)


def test_exact_sat_distinguishes_next_binary64_plane_outside_box():
    bounds = BoundingBox(xmin=0, xmax=1, ymin=0, ymax=1, zmin=0, zmax=1)
    outside = math.nextafter(1.0, math.inf)
    triangle = [[outside, 0.2, 0.2], [outside, 0.8, 0.2], [outside, 0.2, 0.8]]
    assert not triangle_overlaps_aabb_exact(triangle, bounds)


def test_exact_sat_rejects_degenerate_triangle():
    bounds = BoundingBox(xmin=0, xmax=1, ymin=0, ymax=1, zmin=0, zmax=1)
    with pytest.raises(ValueError, match="Degenerate triangle"):
        triangle_overlaps_aabb_exact([[0, 0, 0], [0.5, 0, 0], [1, 0, 0]], bounds)


def test_outward_expansion_never_shrinks_requested_margin():
    bounds = BoundingBox(xmin=1, xmax=2, ymin=3, ymax=4, zmin=5, zmax=6)
    margin = 1e-4
    expanded = outward_expanded_bounds(bounds, margin)
    assert expanded.xmin < bounds.xmin - margin
    assert expanded.ymin < bounds.ymin - margin
    assert expanded.zmin < bounds.zmin - margin
    assert expanded.xmax > bounds.xmax + margin
    assert expanded.ymax > bounds.ymax + margin
    assert expanded.zmax > bounds.zmax + margin


def test_overlapping_aabbs_can_have_exactly_separated_solids():
    vehicle = BoundingBox(xmin=0, xmax=1, ymin=0, ymax=1, zmin=0, zmax=1)
    # All three axis intervals overlap [0.9, 1.0], but the tetrahedron lies on
    # the far side of x+y+z=3.9 while the vehicle has x+y+z<=3.
    tetra = _tetrahedron(
        [
            (0.9, 1.5, 1.5),
            (1.5, 0.9, 1.5),
            (1.5, 1.5, 0.9),
            (1.5, 1.5, 1.5),
        ]
    )
    evidence = prove_mesh_clearance_from_box(tetra, vehicle, 1e-4)
    assert evidence["status"] == "SEPARATED"
    assert evidence["method"] == "EXACT_BINARY64_13_AXIS_SAT_PLUS_BOOLEAN_CONTAINMENT"


def test_clearance_envelope_rejects_near_but_nonintersecting_solid():
    vehicle = BoundingBox(xmin=0, xmax=1, ymin=0, ymax=1, zmin=0, zmax=1)
    nearby = _box(
        extents=(0.2, 0.4, 0.4),
        translation=(1.10005, 0.5, 0.5),
    )
    evidence = prove_mesh_clearance_from_box(nearby, vehicle, 1e-4)
    assert evidence["status"] == "CLEARANCE_VIOLATION"
    assert evidence["witness"]["triangle_index"] >= 0


def test_boolean_containment_catches_box_inside_geom_without_surface_crossing():
    vehicle = BoundingBox(xmin=0, xmax=1, ymin=0, ymax=1, zmin=0, zmax=1)
    enclosing = _box(extents=(4, 4, 4), translation=(0.5, 0.5, 0.5))
    evidence = prove_mesh_clearance_from_box(enclosing, vehicle, 1e-4)
    assert evidence["status"] == "CLEARANCE_VIOLATION"
    assert evidence["containment_overlap_volume_m3"] > 0
