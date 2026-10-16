"""Mesh inspection without repairs or bounding-box substitutes."""

import numpy as np
import trimesh
from ifc_to_fds.core.canonical import BoundingBox, TriangleMesh


def as_trimesh(mesh):
    return trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces, process=False)


def bounds_for_vertices(vertices):
    if not vertices:
        return None
    v = np.asarray(vertices, dtype=float)
    if v.ndim != 2 or v.shape[1] != 3 or not np.isfinite(v).all():
        return None
    lo, hi = v.min(axis=0), v.max(axis=0)
    if np.any(hi <= lo):
        return None
    return BoundingBox(
        xmin=lo[0], xmax=hi[0], ymin=lo[1], ymax=hi[1], zmin=lo[2], zmax=hi[2]
    )


def inspect_mesh_quality(mesh):
    result = dict(
        degenerate_faces=0,
        invalid_indices=0,
        open_edges=0,
        non_manifold_edges=0,
        inconsistent_edges=0,
        is_closed_manifold=0,
        positive_volume=0,
        finite=1,
    )
    verts = np.asarray(mesh.vertices, dtype=float)
    if verts.ndim != 2 or verts.shape[1:] != (3,) or not np.isfinite(verts).all():
        result["finite"] = 0
        return result
    edges = {}
    directed = set()
    for face in mesh.faces:
        if len(face) != 3 or any(i < 0 or i >= len(verts) for i in face):
            result["invalid_indices"] += 1
            continue
        a, b, c = face
        if (
            len(set(face)) != 3
            or np.linalg.norm(np.cross(verts[b] - verts[a], verts[c] - verts[a]))
            < 1e-12
        ):
            result["degenerate_faces"] += 1
        for x, y in ((a, b), (b, c), (c, a)):
            edge = tuple(sorted((x, y)))
            edges[edge] = edges.get(edge, 0) + 1
            if (x, y) in directed:
                result["inconsistent_edges"] += 1
            directed.add((x, y))
    result["open_edges"] = sum(v == 1 for v in edges.values())
    result["non_manifold_edges"] = sum(v > 2 for v in edges.values())
    result["is_closed_manifold"] = int(
        bool(mesh.faces)
        and not any(
            result[k]
            for k in (
                "degenerate_faces",
                "invalid_indices",
                "open_edges",
                "non_manifold_edges",
                "inconsistent_edges",
            )
        )
    )
    if result["is_closed_manifold"]:
        result["positive_volume"] = int(as_trimesh(mesh).volume > 1e-12)
    return result


def valid_solid(mesh):
    q = inspect_mesh_quality(mesh)
    return bool(q["finite"] and q["is_closed_manifold"] and q["positive_volume"])


def box_mesh(bounds):
    b = trimesh.creation.box(extents=[bounds.dx, bounds.dy, bounds.dz])
    b.apply_translation(
        [
            (bounds.xmin + bounds.xmax) / 2,
            (bounds.ymin + bounds.ymax) / 2,
            (bounds.zmin + bounds.zmax) / 2,
        ]
    )
    return TriangleMesh(vertices=b.vertices.tolist(), faces=b.faces.tolist())


def is_axis_aligned_box(mesh, tolerance=1e-6):
    if not mesh or not valid_solid(mesh):
        return False
    tm = as_trimesh(mesh)
    bounds = bounds_for_vertices(mesh.vertices)
    if bounds is None:
        return False
    # Every face lies on one of the six box planes; no concave bounding-box proxy.
    for triangle in tm.triangles:
        if not any(
            np.all(np.abs(triangle[:, axis] - plane) <= tolerance)
            for axis in range(3)
            for plane in tm.bounds[:, axis]
        ):
            return False
    return abs(tm.volume - bounds.volume) <= max(1e-12, bounds.volume * 1e-6)


def intersects_box(mesh, bounds):
    if not valid_solid(mesh):
        raise ValueError("Cannot prove intersection for an invalid solid")
    a = as_trimesh(mesh)
    b = as_trimesh(box_mesh(bounds))
    hit = trimesh.boolean.intersection([a, b], engine="manifold")
    return hit.volume > 1e-12


def has_self_intersection(mesh):
    """Detect nonadjacent triangle crossings and overlapping closed components."""
    tm = as_trimesh(mesh)
    triangles = tm.triangles
    tree = tm.triangles_tree
    faces = np.asarray(mesh.faces)

    def segment_hit(start, end, triangle):
        direction = end - start
        edge1, edge2 = triangle[1] - triangle[0], triangle[2] - triangle[0]
        h = np.cross(direction, edge2)
        det = np.dot(edge1, h)
        if abs(det) < 1e-12:
            return False
        u = np.dot(start - triangle[0], h) / det
        q = np.cross(start - triangle[0], edge1)
        v = np.dot(direction, q) / det
        t = np.dot(edge2, q) / det
        return 1e-8 < t < 1 - 1e-8 and u >= -1e-8 and v >= -1e-8 and u + v <= 1 + 1e-8

    for i, tri in enumerate(triangles):
        bounds = np.r_[tri.min(axis=0), tri.max(axis=0)]
        for j in tree.intersection(bounds):
            if j <= i or set(faces[i]) & set(faces[j]):
                continue
            other = triangles[j]
            normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            if np.max(np.abs((other - tri[0]) @ normal)) < 1e-10 * np.linalg.norm(
                normal
            ):
                from shapely.geometry import Polygon

                axes = [x for x in range(3) if x != np.argmax(np.abs(normal))]
                if (
                    Polygon(tri[:, axes]).intersection(Polygon(other[:, axes])).area
                    > 1e-12
                ):
                    return True
            for a, b in ((0, 1), (1, 2), (2, 0)):
                if segment_hit(tri[a], tri[b], other) or segment_hit(
                    other[a], other[b], tri
                ):
                    return True
    components = tm.split()
    if len(components) > 1:
        union = trimesh.boolean.union(list(components), engine="manifold")
        if sum(abs(c.volume) for c in components) - union.volume > 1e-9:
            return True
    return False
