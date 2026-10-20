"""Mesh inspection without repairs or bounding-box substitutes."""

import numpy as np
import trimesh
from fractions import Fraction
from contextvars import ContextVar
from contextlib import contextmanager
import hashlib
from copy import deepcopy
from ifc_to_fds.core.canonical import BoundingBox, TriangleMesh
from .boolean import solid_boolean


_intersection_evidence = ContextVar("intersection_evidence", default=None)
_intersection_witness = ContextVar("intersection_witness", default=None)


@contextmanager
def mesh_evidence_scope():
    """Reuse pure proofs only during this audit, keyed by complete mesh bytes.

    IFC extraction still runs independently. No source model, mesh, or result
    from another audit is retained; edited vertices/faces produce a different key.
    """
    token = _intersection_evidence.set({})
    try:
        yield
    finally:
        _intersection_evidence.reset(token)


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
    triangles = [face for face in mesh.faces if len(face) == 3]
    result["invalid_indices"] = len(mesh.faces) - len(triangles)
    # Filter before int64 conversion; arbitrarily large Python indices remain
    # invalid input instead of overflowing the accelerated path.
    usable = [f for f in triangles if all(0 <= i < len(verts) for i in f)]
    result["invalid_indices"] += len(triangles) - len(usable)
    if usable:
        faces = np.asarray(usable, dtype=np.int64)
        a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        repeated = (
            (faces[:, 0] == faces[:, 1])
            | (faces[:, 1] == faces[:, 2])
            | (faces[:, 2] == faces[:, 0])
        )
        result["degenerate_faces"] = int(
            np.count_nonzero(
                repeated | (np.linalg.norm(np.cross(b - a, c - a), axis=1) < 1e-12)
            )
        )
        directed = np.concatenate(
            (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])
        )
        _, occurrences = np.unique(directed, axis=0, return_counts=True)
        result["inconsistent_edges"] = int(np.sum(occurrences - 1))
        _, occurrences = np.unique(
            np.sort(directed, axis=1), axis=0, return_counts=True
        )
        result["open_edges"] = int(np.count_nonzero(occurrences == 1))
        result["non_manifold_edges"] = int(np.count_nonzero(occurrences > 2))
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
    hit = solid_boolean([a, b], "intersection")
    return hit.volume > 1e-12


def has_self_intersection(mesh, details=None):
    """Compatibility predicate. Numerical/backend uncertainty raises, never FAILs."""
    if details is None:
        details = _intersection_witness.get()

    def witness(kind, **values):
        if details is not None:
            details.update(kind=kind, **values)
        return True

    tm = as_trimesh(mesh)
    triangles = tm.triangles
    tree = tm.triangles_tree
    faces = np.asarray(mesh.faces)

    def plane_side(triangle, point):
        for axis in range(3):
            if triangle[0, axis] == triangle[1, axis] == triangle[2, axis]:
                # Axis-aligned planes have an exact binary64 sign comparison.
                return int(point[axis] > triangle[0, axis]) - int(
                    point[axis] < triangle[0, axis]
                )
        vectors = np.asarray(
            [triangle[1] - triangle[0], triangle[2] - triangle[0], point - triangle[0]]
        )
        a, b, c = vectors
        terms = [
            a[0] * b[1] * c[2],
            a[1] * b[2] * c[0],
            a[2] * b[0] * c[1],
            -a[2] * b[1] * c[0],
            -a[1] * b[0] * c[2],
            -a[0] * b[2] * c[1],
        ]
        value = sum(terms)
        error = sum(abs(x) for x in terms) * np.finfo(float).eps * 16
        if abs(value) > error:
            return 1 if value > 0 else -1
        # Exact arithmetic over the original binary64 coordinates, including
        # subtraction. A distance epsilon cannot establish coplanarity.
        origin = [Fraction(float(x)) for x in triangle[0]]
        a, b, c = [
            [Fraction(float(x)) - o for x, o in zip(p, origin)]
            for p in (triangle[1], triangle[2], point)
        ]
        exact = (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
        return (exact > 0) - (exact < 0)

    def segment_hit(start, end, triangle):
        direction = end - start
        edge1, edge2 = triangle[1] - triangle[0], triangle[2] - triangle[0]
        h = np.cross(direction, edge2)
        det = np.dot(edge1, h)
        q = np.cross(start - triangle[0], edge1)
        numerators = np.asarray(
            [np.dot(start - triangle[0], h), np.dot(direction, q), np.dot(edge2, q)]
        )
        bound = (
            64
            * np.finfo(float).eps
            * max(
                float(
                    np.linalg.norm(edge1)
                    * np.linalg.norm(edge2)
                    * np.linalg.norm(direction)
                ),
                float(np.max(np.abs(numerators))),
                np.finfo(float).tiny,
            )
        )
        if abs(det) > bound:
            u, v, t = numerators / det
            margin = bound / abs(det)
            if min(u, v, t, 1 - t, 1 - u - v) > margin:
                return True
            if min(u, v, t, 1 - t, 1 - u - v) < -margin:
                return False

        # Uncertain ratios use exact rational predicates, not widened barycentric
        # tolerances. The endpoint rule is strict as in the original traversal.
        def vector(p):
            return tuple(Fraction(float(x)) for x in p)

        def sub(a, b):
            return tuple(x - y for x, y in zip(a, b))

        def cross(a, b):
            return (
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0],
            )

        def dot(a, b):
            return sum(x * y for x, y in zip(a, b))

        p0, p1, p2 = map(vector, triangle)
        origin = vector(start)
        direction = sub(vector(end), origin)
        edge1, edge2, offset = sub(p1, p0), sub(p2, p0), sub(origin, p0)
        h, q = cross(direction, edge2), cross(offset, edge1)
        determinant = dot(edge1, h)
        if not determinant:
            return False
        u, v, t = (
            dot(offset, h) / determinant,
            dot(direction, q) / determinant,
            dot(edge2, q) / determinant,
        )
        return 0 < t < 1 and u >= 0 and v >= 0 and u + v <= 1

    for i, tri in enumerate(triangles):
        bounds = np.r_[tri.min(axis=0), tri.max(axis=0)]
        for j in tree.intersection(bounds):
            if j <= i:
                continue
            other = triangles[j]
            sides = [plane_side(tri, p) for p in other]
            reverse_sides = [plane_side(other, p) for p in tri]
            if (
                all(s > 0 for s in sides)
                or all(s < 0 for s in sides)
                or all(s > 0 for s in reverse_sides)
                or all(s < 0 for s in reverse_sides)
            ):
                continue
            if len(set(faces[i]) & set(faces[j])) >= 2 and any(sides):
                # Distinct planes with a shared edge intersect on that edge only.
                continue
            normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            if not any(sides):
                from shapely.geometry import Polygon

                axes = [x for x in range(3) if x != np.argmax(np.abs(normal))]
                area = Polygon(tri[:, axes]).intersection(Polygon(other[:, axes])).area
                if area > 0:
                    return witness("COPLANAR_FACE_OVERLAP", triangles=[int(i), int(j)], projected_area_m2=float(area))
                # Exact coplanarity and zero projected area prove no interior
                # overlap. Segment/triangle ratios are singular on this plane.
                continue
            for a, b in ((0, 1), (1, 2), (2, 0)):
                if segment_hit(tri[a], tri[b], other) or segment_hit(
                    other[a], other[b], tri
                ):
                    return witness("TRIANGLE_CROSSING", triangles=[int(i), int(j)])
    # Trimesh's default split repairs holes. Inspection must preserve source
    # topology and must not depend on an optional repair backend (networkx).
    components = tm.split(only_watertight=False, repair=False)
    if len(components) > 1:
        for i, component in enumerate(components):
            for j, other in enumerate(components[i + 1 :], i + 1):
                if np.any(component.bounds[1] <= other.bounds[0]) or np.any(
                    other.bounds[1] <= component.bounds[0]
                ):
                    continue
                if component.is_volume and other.is_volume:
                    volume = solid_boolean([component, other], "intersection").volume
                    if volume > 0:
                        return witness("COMPONENT_VOLUME_OVERLAP", components=[i, j], volume_m3=float(volume))
    return False


def self_intersection_evidence(mesh):
    """Three-way evidence consumed by the independent validator."""
    cache = _intersection_evidence.get()
    key = None
    if cache is not None:
        try:
            vertices = np.asarray(mesh.vertices, dtype="<f8")
            faces = np.asarray(mesh.faces, dtype="<i8")
            digest = hashlib.sha256()
            digest.update(str((vertices.shape, faces.shape)).encode("ascii"))
            digest.update(vertices.tobytes())
            digest.update(faces.tobytes())
            key = digest.digest()
        except (ValueError, TypeError, OverflowError):
            pass  # Invalid inputs still receive the ordinary three-way result.
        if key is not None and key in cache:
            return deepcopy(cache[key])
    details = {}
    token = _intersection_witness.set(details)
    try:
        hit = has_self_intersection(mesh)
        result = {
            "status": "CONFIRMED" if hit else "CLEAN",
            "method": "adaptive-exact-plane/triangle-crossing/manifold-components-v1",
        }
        if details:
            result["witness"] = details
    except Exception as exc:
        result = {"status": "UNCERTAIN", "reason": str(exc)}
    finally:
        _intersection_witness.reset(token)
    if cache is not None and key is not None and result["status"] != "UNCERTAIN":
        if len(cache) >= 4096:
            cache.pop(next(iter(cache)))
        cache[key] = deepcopy(result)
    return result
