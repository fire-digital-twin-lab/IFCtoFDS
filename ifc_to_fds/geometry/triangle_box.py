"""Exact binary64 triangle/AABB predicates for fail-closed clearance proofs.

The triangle-box overlap predicate implements the 13-axis Separating Axis
Theorem (SAT) described by Akenine-Moller. Input coordinates are converted from
their binary64 values to exact rational numbers before the SAT projections, so
the predicate itself does not introduce an arbitrary geometric epsilon.

This module deliberately separates:
- surface overlap/contact: exact rational triangle-vs-AABB SAT;
- containment without surface crossing: the repository's reviewed solid boolean
  backend, used only after no triangle touches the box.

The clearance box is rounded outward after expansion so floating-point rounding
can only make the rejection region more conservative, never smaller.
"""

from __future__ import annotations

from fractions import Fraction
import math
from typing import Any

import numpy as np

from ifc_to_fds.domain.bim import BoundingBox, TriangleMesh
from ifc_to_fds.geometry.boolean import solid_boolean
from ifc_to_fds.geometry.mesh import (
    as_trimesh,
    mesh_volume,
    box_mesh,
    self_intersection_evidence,
    valid_solid,
)


def _fraction(value: float) -> Fraction:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Triangle/AABB evidence requires finite coordinates")
    return Fraction(value)


def _sub(left, right):
    return tuple(a - b for a, b in zip(left, right))


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _separated(axis, vertices, half_extents) -> bool:
    """Return whether one exact SAT axis strictly separates triangle and box."""

    if not any(axis):
        return False
    projections = [_dot(vertex, axis) for vertex in vertices]
    radius = sum(
        half_extents[index] * abs(axis[index])
        for index in range(3)
    )
    return max(projections) < -radius or min(projections) > radius


def triangle_overlaps_aabb_exact(
    triangle: Any,
    bounds: BoundingBox,
) -> bool:
    """Test triangle/AABB overlap including boundary contact.

    The 13 SAT axes are:
    - three AABB face normals;
    - the triangle face normal;
    - nine cross products between the three AABB axes and triangle edges.

    A degenerate triangle cannot provide reviewed collision evidence and is
    rejected rather than silently classified.
    """

    array = np.asarray(triangle, dtype=float)
    if array.shape != (3, 3) or not np.isfinite(array).all():
        raise ValueError("Triangle must contain three finite 3D vertices")

    mins = (
        _fraction(bounds.xmin),
        _fraction(bounds.ymin),
        _fraction(bounds.zmin),
    )
    maxs = (
        _fraction(bounds.xmax),
        _fraction(bounds.ymax),
        _fraction(bounds.zmax),
    )
    center = tuple((low + high) / 2 for low, high in zip(mins, maxs))
    half_extents = tuple((high - low) / 2 for low, high in zip(mins, maxs))

    vertices = [
        tuple(_fraction(coordinate) for coordinate in point)
        for point in array
    ]
    vertices = [_sub(vertex, center) for vertex in vertices]

    edges = (
        _sub(vertices[1], vertices[0]),
        _sub(vertices[2], vertices[1]),
        _sub(vertices[0], vertices[2]),
    )
    triangle_normal = _cross(edges[0], _sub(vertices[2], vertices[0]))
    if not any(triangle_normal):
        raise ValueError("Degenerate triangle cannot establish collision evidence")

    box_axes = (
        (Fraction(1), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(1)),
    )
    axes = [*box_axes, triangle_normal]
    axes.extend(_cross(box_axis, edge) for box_axis in box_axes for edge in edges)

    return not any(
        _separated(axis, vertices, half_extents)
        for axis in axes
    )


def outward_expanded_bounds(bounds: BoundingBox, margin_m: float) -> BoundingBox:
    """Expand by at least margin_m in each axis after binary64 rounding."""

    margin = float(margin_m)
    if not math.isfinite(margin) or margin < 0:
        raise ValueError("Clearance margin must be finite and non-negative")

    def lower(value):
        return math.nextafter(float(value) - margin, -math.inf)

    def upper(value):
        return math.nextafter(float(value) + margin, math.inf)

    return BoundingBox(
        xmin=lower(bounds.xmin),
        xmax=upper(bounds.xmax),
        ymin=lower(bounds.ymin),
        ymax=upper(bounds.ymax),
        zmin=lower(bounds.zmin),
        zmax=upper(bounds.zmax),
    )


def prove_mesh_clearance_from_box(
    mesh: TriangleMesh,
    bounds: BoundingBox,
    clearance_m: float,
) -> dict[str, Any]:
    """Prove a valid solid lies outside a conservatively expanded AABB.

    SEPARATED proves that:
    1. no source triangle touches/intersects the outward-expanded box under the
       exact binary64 SAT predicate; and
    2. the expanded box is not contained in the solid, established through the
       reviewed solid-boolean backend.

    A non-clean or numerically unavailable operand raises so callers can remain
    fail-closed.
    """

    if not valid_solid(mesh):
        raise ValueError("Verified GEOM collision evidence requires a valid solid")

    self_intersection = self_intersection_evidence(mesh)
    if self_intersection["status"] == "CONFIRMED":
        raise ValueError("Verified GEOM collision mesh is self-intersecting")
    if self_intersection["status"] == "UNCERTAIN":
        raise RuntimeError(
            "Verified GEOM self-intersection evidence is uncertain: "
            + str(self_intersection.get("reason", "unknown"))
        )

    expanded = outward_expanded_bounds(bounds, clearance_m)
    triangles = as_trimesh(mesh).triangles
    minimum = np.asarray([expanded.xmin, expanded.ymin, expanded.zmin])
    maximum = np.asarray([expanded.xmax, expanded.ymax, expanded.zmax])

    triangle_minimum = triangles.min(axis=1)
    triangle_maximum = triangles.max(axis=1)
    candidates = np.flatnonzero(
        np.all(triangle_maximum >= minimum, axis=1)
        & np.all(triangle_minimum <= maximum, axis=1)
    )

    for index in candidates.tolist():
        if triangle_overlaps_aabb_exact(triangles[index], expanded):
            return {
                "status": "CLEARANCE_VIOLATION",
                "method": "EXACT_BINARY64_13_AXIS_SAT",
                "clearance_m": float(clearance_m),
                "expanded_bounds": expanded.model_dump(),
                "candidate_triangles": int(len(candidates)),
                "witness": {"triangle_index": int(index)},
            }

    try:
        intersection = solid_boolean(
            [as_trimesh(mesh), as_trimesh(box_mesh(expanded))],
            "intersection",
        )
    except (ValueError, RuntimeError, TypeError) as exc:
        raise RuntimeError(
            "GEOM containment boolean unavailable after exact surface SAT"
        ) from exc

    overlap_volume = max(0.0, mesh_volume(intersection))
    if overlap_volume > 1e-12:
        return {
            "status": "CLEARANCE_VIOLATION",
            "method": "EXACT_BINARY64_13_AXIS_SAT_PLUS_BOOLEAN_CONTAINMENT",
            "clearance_m": float(clearance_m),
            "expanded_bounds": expanded.model_dump(),
            "candidate_triangles": int(len(candidates)),
            "containment_overlap_volume_m3": overlap_volume,
        }

    return {
        "status": "SEPARATED",
        "method": "EXACT_BINARY64_13_AXIS_SAT_PLUS_BOOLEAN_CONTAINMENT",
        "clearance_m": float(clearance_m),
        "expanded_bounds": expanded.model_dump(),
        "candidate_triangles": int(len(candidates)),
        "containment_overlap_volume_m3": overlap_volume,
    }


__all__ = [
    "outward_expanded_bounds",
    "prove_mesh_clearance_from_box",
    "triangle_overlaps_aabb_exact",
]
