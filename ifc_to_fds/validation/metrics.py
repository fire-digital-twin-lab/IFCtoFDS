"""Solid measurements; failed booleans never fall back to bounds."""

import numpy as np
import trimesh
from ifc_to_fds.geometry.boolean import solid_boolean
from ifc_to_fds.geometry.mesh import (
    as_trimesh,
    valid_solid,
    is_axis_aligned_box,
    self_intersection_evidence,
)


class SelfIntersectionError(ValueError):
    def __init__(self, evidence, operand):
        self.evidence = {**evidence, "operand": operand}
        # Keep the stable finding title; precise witnesses are structured metrics.
        super().__init__("Self-intersecting solid")


def calculate_bbox_iou(b1, b2):
    if not b1 or not b2:
        return 0.0
    intersection = np.maximum(
        0,
        np.minimum([b1.xmax, b1.ymax, b1.zmax], [b2.xmax, b2.ymax, b2.zmax])
        - np.maximum([b1.xmin, b1.ymin, b1.zmin], [b2.xmin, b2.ymin, b2.zmin]),
    ).prod()
    return float(intersection / (b1.volume + b2.volume - intersection))


def same_surface_partition(a, b):
    """Prove equality of coplanar polygon unions despite vertex/triangle order.

    Only identical supporting planes are admitted. Unsupported near-coplanar
    surfaces fall through to sampled/inconclusive measurements.
    """

    def triangle_set(mesh):
        return sorted(
            tuple(sorted(tuple(float(x) for x in point) for point in triangle))
            for triangle in mesh.triangles
        )

    if triangle_set(a) == triangle_set(b):
        return True
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    def patches(mesh):
        groups = {}
        for triangle, normal in zip(mesh.triangles, mesh.face_normals):
            normal = normal.copy()
            axis = int(np.argmax(np.abs(normal)))
            if normal[axis] < 0:
                normal *= -1
            distance = float(np.dot(normal, triangle[0]))
            key = tuple(np.round(np.r_[normal, distance], 10))
            groups.setdefault(key, []).append((triangle, normal, distance, axis))
        return groups

    left, right = patches(a), patches(b)
    if left.keys() != right.keys():
        return False
    for key in left:
        pieces = left[key] + right[key]
        _, normal, distance, axis = pieces[0]
        if any(not np.array_equal(n, normal) or d != distance for _, n, d, _ in pieces):
            return False
        axes = [i for i in range(3) if i != axis]
        one = unary_union([Polygon(t[:, axes]) for t, _, _, _ in left[key]])
        two = unary_union([Polygon(t[:, axes]) for t, _, _, _ in right[key]])
        if not one.equals(two):
            return False
    return True


def compare_solids(reference, outputs):
    if (
        not valid_solid(reference)
        or not outputs
        or not all(valid_solid(m) for m in outputs)
    ):
        raise ValueError("Cannot measure invalid solids")
    a = as_trimesh(reference)
    pieces = [as_trimesh(m) for m in outputs]
    exact_identity = (
        len(pieces) == 1
        and np.array_equal(a.vertices, pieces[0].vertices)
        and np.array_equal(a.faces, pieces[0].faces)
    )
    # Independently read, exactly equal oriented triangles describe the same
    # surface. One self-intersection proof covers both; changed outputs must
    # still receive their own proof. No tolerance or bounding-box shortcut.
    for index, mesh in enumerate([reference] if exact_identity else [reference, *outputs]):
        evidence = self_intersection_evidence(mesh)
        if evidence["status"] == "CONFIRMED":
            raise SelfIntersectionError(evidence, "source" if index == 0 else f"output:{index}")
        if evidence["status"] == "UNCERTAIN":
            raise RuntimeError(f"Self-intersection uncertain: {evidence['reason']}")
    b = pieces[0] if len(pieces) == 1 else solid_boolean(pieces, "union")
    if exact_identity:
        # Independently reconstructed coordinates and oriented triangles are equal.
        # This is a full-surface identity proof, not a sampled/bounds shortcut.
        components = len(a.split(only_watertight=False, repair=False))
        return dict(
            solid_iou=1.0,
            relative_volume_error=0.0,
            relative_area_error=0.0,
            surface_distance_m=0.0,
            surface_proven=True,
            reference_components=components,
            output_components=components,
            comparison_method="EXACT_ORIENTED_TRIANGLES",
        )
    intersection = solid_boolean([a, b], "intersection")
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
    partition_equivalent = False
    if not correspondence and not box_equivalent:
        partition_equivalent = same_surface_partition(a, b)
    if partition_equivalent:
        surface = 0.0
    elif correspondence:
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
        surface_proven=bool(correspondence or box_equivalent or partition_equivalent),
        reference_components=len(a.split(only_watertight=False, repair=False)),
        output_components=len(b.split(only_watertight=False, repair=False)),
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
            float(solid_boolean([as_trimesh(host), void], "intersection").volume),
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


class SolidCandidateIndex:
    """Audit-local broad phase only. Exact Boolean checks still decide passage."""

    def __init__(self, meshes):
        from rtree.index import Index, Property

        self.meshes = list(meshes)
        self.tree = Index(properties=Property(dimension=3))
        self.unbounded = False
        for i, mesh in enumerate(self.meshes):
            vertices = np.asarray(mesh.vertices, dtype=float)
            if (
                vertices.ndim != 2
                or vertices.shape[1:] != (3,)
                or not len(vertices)
                or not np.isfinite(vertices).all()
            ):
                self.unbounded = True
                continue
            self.tree.insert(
                i, np.r_[vertices.min(axis=0), vertices.max(axis=0)].tolist()
            )

    def candidates(self, bounds):
        if self.unbounded:
            raise RuntimeError(
                "Cannot bound an audit obstacle; passage candidates uncertain"
            )
        return [
            self.meshes[i]
            for i in sorted(
                self.tree.intersection(np.r_[bounds[0], bounds[1]].tolist())
            )
        ]


def passage_metrics(reference_meshes, output_meshes, opening):
    """Compare entire free volumes, including source door/window fills and blockers."""
    void = as_trimesh(opening)

    def free_volume(meshes):
        pieces = []
        if isinstance(meshes, SolidCandidateIndex):
            meshes = meshes.candidates(void.bounds)
        for mesh in meshes:
            tm = as_trimesh(mesh)
            if np.any(tm.bounds[1] <= void.bounds[0]) or np.any(
                tm.bounds[0] >= void.bounds[1]
            ):
                continue
            if not valid_solid(mesh):
                raise ValueError("Invalid obstacle near source opening")
            intersection = solid_boolean([void, tm], "intersection")
            if intersection.volume > 1e-12:
                pieces.append(intersection)
        if not pieces:
            return void
        return solid_boolean([void, *pieces], "difference")

    a, b = free_volume(reference_meshes), free_volume(output_meshes)
    intersection = (
        solid_boolean([a, b], "intersection") if len(a.faces) and len(b.faces) else None
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
