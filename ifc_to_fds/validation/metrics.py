"""Solid measurements; failed booleans never fall back to bounds."""

import numpy as np
import trimesh
from ifc_to_fds.geometry.mesh import (
    as_trimesh,
    valid_solid,
    is_axis_aligned_box,
    has_self_intersection,
)


def calculate_bbox_iou(b1, b2):
    if not b1 or not b2:
        return 0.0
    intersection = np.maximum(
        0,
        np.minimum([b1.xmax, b1.ymax, b1.zmax], [b2.xmax, b2.ymax, b2.zmax])
        - np.maximum([b1.xmin, b1.ymin, b1.zmin], [b2.xmin, b2.ymin, b2.zmin]),
    ).prod()
    return float(intersection / (b1.volume + b2.volume - intersection))


def compare_solids(reference, outputs):
    if (
        not valid_solid(reference)
        or not outputs
        or not all(valid_solid(m) for m in outputs)
    ):
        raise ValueError("Cannot measure invalid solids")
    if has_self_intersection(reference) or any(
        has_self_intersection(m) for m in outputs
    ):
        raise ValueError("Self-intersecting solid")
    a = as_trimesh(reference)
    pieces = [as_trimesh(m) for m in outputs]
    b = (
        pieces[0]
        if len(pieces) == 1
        else trimesh.boolean.union(pieces, engine="manifold")
    )
    intersection = trimesh.boolean.intersection([a, b], engine="manifold")
    vi = max(0.0, float(intersection.volume))
    union = float(a.volume + b.volume - vi)
    # Corresponding triangles give a direct bound over entire surfaces. For
    # different triangulations sampled distance detects defects but cannot prove PASS.
    correspondence = (
        len(outputs) == 1
        and a.vertices.shape == b.vertices.shape
        and np.array_equal(a.faces, b.faces)
    )
    box_equivalent = (
        len(outputs) == 1
        and is_axis_aligned_box(reference)
        and is_axis_aligned_box(outputs[0])
    )
    if correspondence:
        surface = float(np.linalg.norm(a.vertices - b.vertices, axis=1).max())
    elif box_equivalent:
        surface = float(np.linalg.norm(a.bounds - b.bounds, axis=1).max())
    else:
        points_a = np.vstack([a.vertices, a.triangles_center])
        points_b = np.vstack([b.vertices, b.triangles_center])
        surface = float(
            max(
                trimesh.proximity.closest_point(b, points_a)[1].max(),
                trimesh.proximity.closest_point(a, points_b)[1].max(),
            )
        )
    return dict(
        solid_iou=vi / union if union > 0 else 0.0,
        relative_volume_error=abs(float(a.volume - b.volume)) / float(a.volume),
        relative_area_error=abs(float(a.area - b.area)) / float(a.area),
        surface_distance_m=surface,
        surface_proven=bool(correspondence or box_equivalent),
        reference_components=len(a.split(only_watertight=False)),
        output_components=len(b.split(only_watertight=False)),
    )


def opening_residual(hosts, opening):
    if not opening or not valid_solid(opening):
        raise ValueError("Opening solid is missing or invalid")
    void = as_trimesh(opening)
    residual = 0.0
    for host in hosts:
        if not valid_solid(host):
            raise ValueError("Invalid host solid")
        residual += max(
            0.0,
            float(
                trimesh.boolean.intersection(
                    [as_trimesh(host), void], engine="manifold"
                ).volume
            ),
        )
    return residual / max(float(void.volume), 1e-12)


def verify_opening_retention(elem):
    if not elem.openings:
        return True
    try:
        return bool(elem.mesh) and all(
            opening_residual([elem.mesh], o.mesh) <= 1e-6 for o in elem.openings
        )
    except (ValueError, RuntimeError):
        return False


def passage_metrics(reference_meshes, output_meshes, opening):
    """Compare entire free volumes, including source door/window fills and blockers."""
    void = as_trimesh(opening)

    def free_volume(meshes):
        pieces = []
        for mesh in meshes:
            tm = as_trimesh(mesh)
            if np.any(tm.bounds[1] <= void.bounds[0]) or np.any(
                tm.bounds[0] >= void.bounds[1]
            ):
                continue
            if not valid_solid(mesh):
                raise ValueError("Invalid obstacle near source opening")
            intersection = trimesh.boolean.intersection([void, tm], engine="manifold")
            if intersection.volume > 1e-12:
                pieces.append(intersection)
        if not pieces:
            return void
        return trimesh.boolean.difference([void, *pieces], engine="manifold")

    a, b = free_volume(reference_meshes), free_volume(output_meshes)
    intersection = (
        trimesh.boolean.intersection([a, b], engine="manifold")
        if len(a.faces) and len(b.faces)
        else None
    )
    overlap = float(intersection.volume) if intersection is not None else 0.0
    return dict(
        source_free_volume_m3=float(a.volume),
        output_free_volume_m3=float(b.volume),
        normalized_symmetric_difference=max(
            0.0, float(a.volume + b.volume - 2 * overlap)
        )
        / max(float(void.volume), 1e-12),
        source_free_components=len(a.split()) if len(a.faces) else 0,
        output_free_components=len(b.split()) if len(b.faces) else 0,
    )
