"""Mesh inspection without repairs or bounding-box substitutes."""

import math
import numpy as np
import trimesh
from fractions import Fraction
from contextvars import ContextVar
from contextlib import contextmanager
import hashlib
from copy import deepcopy
from ifc_to_fds.core.canonical import BoundingBox, TriangleMesh
from .boolean import solid_boolean

# Guard against trimesh zero-volume divide-by-zero bug (DEBT-06 / WP-P0-03)
_orig_mass_properties = trimesh.triangles.mass_properties


def _safe_mass_properties(
    triangles, crosses=None, density=None, center_mass=None, skip_inertia=False
):
    with np.errstate(divide="ignore", invalid="ignore"):
        result = _orig_mass_properties(
            triangles,
            crosses=crosses,
            density=density,
            center_mass=center_mass,
            skip_inertia=skip_inertia,
        )
        if not np.all(np.isfinite(result.center_mass)):
            t = np.asanyarray(triangles, dtype=np.float64)
            result.center_mass = t.mean(axis=(0, 1)) if len(t) > 0 else np.zeros(3)
        return result


trimesh.triangles.mass_properties = _safe_mass_properties


def safe_unit_normals(vectors, epsilon=1e-14, default=(0.0, 0.0, 1.0)):
    """Computes unit normal vectors safely guarding against degenerate or zero-length inputs.

    Parameters
    ----------
    vectors : array_like
        A 3D vector or array of 3D vectors to normalize.
    epsilon : float, optional
        Threshold below which vector length is treated as degenerate (default: 1e-14).
    default : tuple of float, optional
        Default unit normal vector for degenerate inputs (default: (0.0, 0.0, 1.0)).

    Returns
    -------
    ndarray
        Array of normalized finite 3D vectors.
    """
    v = np.asarray(vectors, dtype=np.float64)
    single = (v.ndim == 1)
    if single:
        v = v.reshape(1, -1)
    if v.shape[-1] != 3:
        raise ValueError(f"Expected 3D vectors with last dimension 3, got shape {v.shape}")

    lengths = np.linalg.norm(v, axis=-1, keepdims=True)
    mask = (lengths > epsilon) & np.isfinite(lengths)
    with np.errstate(divide="ignore", invalid="ignore"):
        safe_lengths = np.where(mask, lengths, 1.0)
        normalized = np.where(mask, v / safe_lengths, np.array(default, dtype=np.float64))

    if single:
        return normalized[0]
    return normalized


# Aliases for flexibility across validation and test callers
safe_normalize_normals = safe_unit_normals
safe_normalize = safe_unit_normals


def compute_face_normals(mesh, epsilon=1e-14, default=(0.0, 0.0, 1.0)):
    """Computes unit face normals for a mesh safely, preventing divide-by-zero on degenerate triangles.

    Parameters
    ----------
    mesh : TriangleMesh, trimesh.Trimesh, or object with vertices and faces
        The triangular mesh representation.
    epsilon : float, optional
        Threshold for degenerate cross product detection (default: 1e-14).
    default : tuple of float, optional
        Default unit normal for zero-area faces (default: (0.0, 0.0, 1.0)).

    Returns
    -------
    ndarray
        Array of shape (N, 3) containing finite unit normals.
    """
    if hasattr(mesh, "vertices") and hasattr(mesh, "faces"):
        verts = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces)
    else:
        raise ValueError("Mesh must provide 'vertices' and 'faces' attributes")

    if len(faces) == 0:
        return np.empty((0, 3), dtype=np.float64)
    if len(verts) == 0:
        return np.full((len(faces), 3), default, dtype=np.float64)

    faces_arr = np.asarray(faces, dtype=np.int64)
    if faces_arr.ndim != 2 or faces_arr.shape[1] != 3:
        normals = np.full((len(faces), 3), default, dtype=np.float64)
        for idx, f in enumerate(faces):
            if len(f) == 3 and all(0 <= i < len(verts) for i in f):
                p0, p1, p2 = verts[f[0]], verts[f[1]], verts[f[2]]
                cross = np.cross(p1 - p0, p2 - p0)
                normals[idx] = safe_unit_normals(cross, epsilon=epsilon, default=default)
        return normals

    p0 = verts[faces_arr[:, 0]]
    p1 = verts[faces_arr[:, 1]]
    p2 = verts[faces_arr[:, 2]]
    cross = np.cross(p1 - p0, p2 - p0)
    return safe_unit_normals(cross, epsilon=epsilon, default=default)


compute_mesh_normals = compute_face_normals


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


def _disconnected_vertex_links(faces, edge_ids):
    """Count vertices whose incident triangles form more than one closed fan."""
    # Directed edges are ordered by local face edge: 0→1, 1→2, 2→0.
    # Join equal corners (face, vertex) across opposite half-edges.
    face_count = len(faces)
    first, second = np.argsort(edge_ids, kind="stable").reshape(-1, 2).T
    corner_count = 3 * face_count
    connections = np.column_stack((
        np.r_[first, second],
        (np.r_[second, first] + face_count) % corner_count,
    ))
    labels = trimesh.graph.connected_component_labels(connections, node_count=corner_count)
    _, representatives = np.unique(labels, return_index=True)
    _, fan_counts = np.unique(faces.T.ravel()[representatives], return_counts=True)
    return int(np.count_nonzero(fan_counts > 1))


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
        _, edge_ids, occurrences = np.unique(
            np.sort(directed, axis=1), axis=0, return_inverse=True, return_counts=True
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
        disconnected = _disconnected_vertex_links(faces, edge_ids)
        if disconnected:
            result["non_manifold_vertices"] = disconnected
            result["is_closed_manifold"] = 0
        else:
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


def _shell_winding_at_point(shell, point):
    """Evaluate the signed solid-angle sum away from the boundary."""
    rays = shell.triangles - point
    lengths = np.linalg.norm(rays, axis=-1)
    if not np.isfinite(lengths).all() or np.any(lengths == 0):
        raise RuntimeError("Shell containment query is numerically unresolved")
    a, b, c = (rays / lengths[..., None]).transpose(1, 0, 2)
    triple = np.einsum("ij,ij->i", a, np.cross(b, c))
    denominator = 1 + np.einsum("ij,ij->i", a, b + c) + np.einsum("ij,ij->i", b, c)
    roundoff = 64 * np.finfo(float).eps
    if np.any((np.abs(triple) <= roundoff) & (denominator <= roundoff)):
        raise RuntimeError("Shell containment query is too close to a triangle")
    winding = math.fsum(np.arctan2(triple, denominator)) / (2 * math.pi)
    integer = round(winding)
    if abs(integer) > 1 or abs(winding - integer) > 1e-8:
        raise RuntimeError("Shell solid-angle sum is unresolved")
    return integer


def _shell_winding_mismatch(shells):
    volumes = [shell.volume for shell in shells]
    if not np.isfinite(volumes).all() or any(volume == 0 for volume in volumes):
        raise RuntimeError("Shell has no resolved signed volume")
    mismatches = []
    for i, shell in enumerate(shells):
        depth = 0
        for j, container in enumerate(shells):
            if not (
                np.all(container.bounds[0] < shell.bounds[0])
                and np.all(container.bounds[1] > shell.bounds[1])
            ):
                continue
            winding = _shell_winding_at_point(container, shell.vertices[0])
            if winding and (winding > 0) != (volumes[j] > 0):
                raise RuntimeError("Shell signed volume and winding disagree")
            depth += abs(winding)
        if (volumes[i] > 0) != (depth % 2 == 0):
            mismatches.append(dict(
                component=i, containment_depth=depth, signed_volume_m3=float(volumes[i]),
            ))
    return mismatches


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
    if not len(triangles):
        return False
    tree = tm.triangles_tree
    faces = np.asarray(mesh.faces)
    shell_labels = None
    shells = None
    contacts = {}
    unresolved_contacts = {}

    def build_shells():
        nonlocal shell_labels, shells
        if shells is None:
            shell_labels = trimesh.graph.connected_component_labels(
                tm.face_adjacency, node_count=len(triangles)
            )
            # Keep source triangles and edge-connected components intact.
            groups = trimesh.grouping.group(shell_labels)
            shells = (
                tm.submesh(groups, only_watertight=False, repair=False)
                if len(groups) > 1 else [tm]
            )

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

    def classify_shell_contact(i, j, projected_area=None):
        build_shells()
        pair = tuple(sorted((int(shell_labels[i]), int(shell_labels[j]))))
        if pair[0] == pair[1]:
            return False
        left, right = (shells[index] for index in pair)
        if not all(s.is_watertight and s.is_winding_consistent for s in (left, right)):
            return False
        if pair in contacts:
            return True
        separated = bool(
            np.any(left.bounds[1] <= right.bounds[0])
            or np.any(right.bounds[1] <= left.bounds[0])
        )
        if projected_area is not None and not separated:
            if (
                projected_area > 0 and left.is_volume and right.is_volume
                and np.dot(tm.face_normals[i], tm.face_normals[j]) > 0
            ):
                # Same outward normals imply a common material neighbourhood
                # just inside both shells, across the positive-area patch.
                return False
            plane = triangles[i]
            left_sides = {plane_side(plane, point) for point in left.vertices}
            right_sides = {plane_side(plane, point) for point in right.vertices}
            separated = (
                left_sides <= {-1, 0} and right_sides <= {0, 1}
                or left_sides <= {0, 1} and right_sides <= {-1, 0}
            )
        info = dict(triangles=[int(i), int(j)], components=list(pair))
        if projected_area is not None:
            info["projected_area_m2"] = float(projected_area)
        if separated:
            contacts[pair] = dict(kind="COMPONENT_BOUNDARY_CONTACT", **info)
            unresolved_contacts.pop(pair, None)
        else:
            unresolved_contacts.setdefault(
                pair, dict(kind="COMPONENT_BOUNDARY_UNRESOLVED", **info)
            )
        return True

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
                return 3  # Transverse hit strictly inside the triangle.
            if min(u, v, t, 1 - t, 1 - u - v) < -margin:
                return 0

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
            return 0
        u, v, t = (
            dot(offset, h) / determinant,
            dot(direction, q) / determinant,
            dot(edge2, q) / determinant,
        )
        margin = min(u, v, 1 - u - v)
        if margin < 0 or not 0 <= t <= 1:
            return 0
        if t in (0, 1):
            return 1  # A shared endpoint is a contact candidate across shells.
        return 2 + int(margin > 0)

    for i, tri in enumerate(triangles):
        bounds = np.r_[tri.min(axis=0), tri.max(axis=0)]
        for j in tree.intersection(bounds):
            if j <= i:
                continue
            if contacts and tuple(sorted((shell_labels[i], shell_labels[j]))) in contacts:
                continue  # The separating half-spaces cover every pair of faces.
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
            normal = safe_unit_normals(np.cross(tri[1] - tri[0], tri[2] - tri[0]))
            if not any(sides):
                from shapely.geometry import Polygon

                axes = [x for x in range(3) if x != np.argmax(np.abs(normal))]
                patch = Polygon(tri[:, axes]).intersection(Polygon(other[:, axes]))
                if not patch.is_empty:
                    area = patch.area
                    if not classify_shell_contact(i, j, area) and area > 0:
                        return witness("COPLANAR_FACE_OVERLAP", triangles=[int(i), int(j)], projected_area_m2=float(area))
                continue
            for a, b in ((0, 1), (1, 2), (2, 0)):
                # An edge with equal endpoint signs stays on one side of the
                # plane or lies in it. Neither case can give a transverse hit.
                hit = 0
                if reverse_sides[a] != reverse_sides[b]:
                    hit = segment_hit(tri[a], tri[b], other)
                if hit != 3 and sides[a] != sides[b]:
                    hit = max(hit, segment_hit(other[a], other[b], tri))
                if hit == 3 or (hit and not classify_shell_contact(i, j) and hit == 2):
                    return witness("TRIANGLE_CROSSING", triangles=[int(i), int(j)])
    build_shells()
    mixed_winding = (
        len(shells) > 1 and tm.is_watertight and tm.is_winding_consistent
        and any(shell.volume <= 0 for shell in shells)
    )
    if mixed_winding and not (contacts or unresolved_contacts):
        mismatches = _shell_winding_mismatch(shells)
        return witness("SHELL_WINDING_MISMATCH", shells=mismatches) if mismatches else False
    if len(shells) > 1 and not mixed_winding:
        for i, component in enumerate(shells):
            for j, other in enumerate(shells[i + 1 :], i + 1):
                if (i, j) in contacts:
                    continue
                if np.any(component.bounds[1] <= other.bounds[0]) or np.any(
                    other.bounds[1] <= component.bounds[0]
                ):
                    continue
                if component.is_volume and other.is_volume:
                    volume = solid_boolean([component, other], "intersection").volume
                    if volume > 0:
                        return witness("COMPONENT_VOLUME_OVERLAP", components=[i, j], volume_m3=float(volume))
    if contacts or unresolved_contacts:
        contact = next(iter((unresolved_contacts or contacts).values()))
        if details is not None:
            details.update(contact)
        raise RuntimeError("Component boundary contact requires a verified solid union")
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
            "method": "adaptive-exact-plane/triangle-crossing/manifold-components-v2",
        }
        if details:
            result["witness"] = details
    except Exception as exc:
        result = {"status": "UNCERTAIN", "reason": str(exc)}
        if details:
            result["witness"] = details
    finally:
        _intersection_witness.reset(token)
    deterministic = (
        result["status"] != "UNCERTAIN"
        or details.get("kind") == "COMPONENT_BOUNDARY_CONTACT"
    )
    if cache is not None and key is not None and deterministic:
        if len(cache) >= 4096:
            cache.pop(next(iter(cache)))
        cache[key] = deepcopy(result)
    return result
