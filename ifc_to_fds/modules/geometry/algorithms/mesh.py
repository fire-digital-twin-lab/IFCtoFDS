"""Mesh inspection without repairs or bounding-box substitutes."""

import numpy as np
import trimesh
from contextvars import ContextVar
from contextlib import contextmanager
import hashlib
from copy import deepcopy
from ifc_to_fds.domain.contracts import BoundingBox, TriangleMesh
from ifc_to_fds.modules.geometry.algorithms.boolean import solid_boolean
from ifc_to_fds.modules.geometry.algorithms.exact_predicates import Binary64Predicates

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
        n = len(verts)
        if n <= np.iinfo(np.int64).max // n:
            # Valid indices make base-n packing injective. Counting 1D integer
            # keys avoids the costly structured-row sort of unique(axis=0).
            keys = directed[:, 0] * n + directed[:, 1]
            result["inconsistent_edges"] = len(keys) - len(np.unique(keys))
            low, high = np.minimum(directed[:, 0], directed[:, 1]), np.maximum(
                directed[:, 0], directed[:, 1]
            )
            _, occurrences = np.unique(low * n + high, return_counts=True)
        else:
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


def _exact_box_surface(mesh):
    """Prove the 12 triangles tile the six faces of an axis-aligned box.

    This requires the actual eight corners and two triangles sharing a diagonal
    on each face. Bounds alone, approximate coordinates and volume are not a
    proof. Winding/manifold checks remain the responsibility of valid_solid.
    """
    if len(mesh.vertices) != 8 or len(mesh.faces) != 12:
        return False
    vertices = [tuple(p) for p in mesh.vertices]
    if len(set(vertices)) != 8 or not np.isfinite(vertices).all():
        return False
    values = [set(p[axis] for p in vertices) for axis in range(3)]
    if any(len(v) != 2 for v in values):
        return False
    planes = {}
    for face in mesh.faces:
        if len(face) != 3 or len(set(face)) != 3 or any(i < 0 or i >= 8 for i in face):
            return False
        triangle = [vertices[i] for i in face]
        flat = [axis for axis in range(3) if len({p[axis] for p in triangle}) == 1]
        if len(flat) != 1:
            return False
        axis = flat[0]
        planes.setdefault((axis, triangle[0][axis]), []).append(set(face))
    if len(planes) != 6:
        return False
    for (axis, _), faces in planes.items():
        if len(faces) != 2 or len(faces[0] | faces[1]) != 4:
            return False
        shared = faces[0] & faces[1]
        if len(shared) != 2:
            return False
        a, b = (vertices[i] for i in shared)
        if any(a[k] == b[k] for k in range(3) if k != axis):
            return False
    return True


def has_self_intersection(mesh, details=None):
    """Compatibility predicate. Numerical/backend uncertainty raises, never FAILs."""
    if details is None:
        details = _intersection_witness.get()

    def witness(kind, **values):
        if details is not None:
            details.update(kind=kind, **values)
        return True

    if _exact_box_surface(mesh):
        if details is not None:
            details["proof"] = "EXACT_BOX_FACE_PARTITION"
        return False
    tm = as_trimesh(mesh)
    triangles = tm.triangles
    tree = tm.triangles_tree
    faces = np.asarray(mesh.faces)
    exact = Binary64Predicates(tm.vertices)

    prepared = [exact.prepare_triangle(triangle) for triangle in triangles]
    points = [[exact.vector(point) for point in triangle] for triangle in triangles]

    for i, tri in enumerate(triangles):
        bounds = np.r_[tri.min(axis=0), tri.max(axis=0)]
        for j in tree.intersection(bounds):
            if j <= i:
                continue
            other = triangles[j]
            sides = [exact.side_prepared(prepared[i], p) for p in points[j]]
            reverse_sides = [exact.side_prepared(prepared[j], p) for p in points[i]]
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
            normal = prepared[i][3]
            if not any(sides):
                from shapely.geometry import Polygon

                axes = [
                    x
                    for x in range(3)
                    if x != max(range(3), key=lambda axis: abs(normal[axis]))
                ]
                area = Polygon(tri[:, axes]).intersection(Polygon(other[:, axes])).area
                if area > 0:
                    return witness(
                        "COPLANAR_FACE_OVERLAP",
                        triangles=[int(i), int(j)],
                        projected_area_m2=float(area),
                    )
                # Exact coplanarity and zero projected area prove no interior
                # overlap. Segment/triangle ratios are singular on this plane.
                continue
            for a, b in ((0, 1), (1, 2), (2, 0)):
                if exact.segment_prepared(
                    points[i][a], points[i][b], prepared[j]
                ) or exact.segment_prepared(points[j][a], points[j][b], prepared[i]):
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
                        return witness(
                            "COMPONENT_VOLUME_OVERLAP",
                            components=[i, j],
                            volume_m3=float(volume),
                        )
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
            "method": "dyadic-exact/box-face-partition/triangle-crossing/manifold-components-v2",
        }
        if not hit and details.get("proof"):
            result["proof"] = details["proof"]
        elif details:
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
