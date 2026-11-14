"""Mesh inspection without repairs or bounding-box substitutes."""

import numpy as np
import trimesh
from contextvars import ContextVar
from contextlib import contextmanager
import hashlib
from copy import deepcopy
from ifc_to_fds.core.canonical import BoundingBox, TriangleMesh
from .boolean import solid_boolean

def safe_center_mass(tm):
    """Center of mass of a trimesh; zero-volume meshes fall back to the triangle-centroid mean.

    trimesh divides by the volume, giving non-finite values (DEBT-06 / WP-P0-03).
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        center = np.asarray(tm.center_mass, dtype=np.float64)
    if np.all(np.isfinite(center)):
        return center
    t = np.asanyarray(tm.triangles, dtype=np.float64)
    return t.mean(axis=(0, 1)) if len(t) > 0 else np.zeros(3)


def mesh_volume(tm):
    """Signed volume of a trimesh without the volume-dividing center-of-mass step.

    `tm.volume` also computes center_mass = moment / volume, which warns (0/0)
    on empty or zero-volume meshes. The volume itself is the same number.
    """
    return float(
        trimesh.triangles.mass_properties(
            tm.triangles, crosses=tm.triangles_cross, center_mass=np.zeros(3),
            skip_inertia=True,
        ).volume
    )


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


def inspect_mesh_quality(mesh):
    """Mesh quality counters, memoized per mesh bytes inside `mesh_evidence_scope`."""
    cache = _intersection_evidence.get()
    key = None if cache is None else _mesh_key(mesh, "quality")
    if key is not None and key in cache:
        return dict(cache[key])
    result = _compute_mesh_quality(mesh)
    if key is not None:
        _cache_store(cache, key, dict(result))
    return result


def _compute_mesh_quality(mesh):
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
    faces = None
    try:  # fast path: a rectangular, in-range int array (the normal case)
        array = np.asarray(mesh.faces, dtype=np.int64)
        if array.ndim == 2 and array.shape[1] == 3 and array.size and array.min() >= 0 and array.max() < len(verts):
            faces = array
    except (ValueError, TypeError, OverflowError):
        pass
    if faces is None:
        triangles = [face for face in mesh.faces if len(face) == 3]
        result["invalid_indices"] = len(mesh.faces) - len(triangles)
        # Filter before int64 conversion; arbitrarily large Python indices remain
        # invalid input instead of overflowing the accelerated path.
        usable = [f for f in triangles if all(0 <= i < len(verts) for i in f)]
        result["invalid_indices"] += len(triangles) - len(usable)
        faces = np.asarray(usable, dtype=np.int64) if usable else None
    if faces is not None:
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
        n = np.int64(len(verts))  # one int64 key per edge: np.unique on 1-D is far faster than axis=0
        _, occurrences = np.unique(directed[:, 0] * n + directed[:, 1], return_counts=True)
        result["inconsistent_edges"] = int(np.sum(occurrences - 1))
        ends = np.sort(directed, axis=1)
        _, occurrences = np.unique(ends[:, 0] * n + ends[:, 1], return_counts=True)
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
        result["positive_volume"] = int(mesh_volume(as_trimesh(mesh)) > 1e-12)
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
    return abs(mesh_volume(tm) - bounds.volume) <= max(1e-12, bounds.volume * 1e-6)


def intersects_box(mesh, bounds):
    if not valid_solid(mesh):
        raise ValueError("Cannot prove intersection for an invalid solid")
    a = as_trimesh(mesh)
    b = as_trimesh(box_mesh(bounds))
    hit = solid_boolean([a, b], "intersection")
    return mesh_volume(hit) > 1e-12


_EPS = np.finfo(float).eps
_UNKNOWN = 2  # float filter could not decide; exact arithmetic is required
_PAIR_CHUNK = 20000
_EDGES = ((0, 1), (1, 2), (2, 0))


def _first_flat_axis(triangles):
    """Per triangle: first axis on which all three coordinates coincide, else -1."""
    flat = (triangles[:, 0, :] == triangles[:, 1, :]) & (
        triangles[:, 1, :] == triangles[:, 2, :]
    )
    return np.where(flat.any(axis=1), flat.argmax(axis=1), -1)


def _plane_sides(tri, pts, axis):
    """Sign of each of the 3 points `pts` (n,3,3) against the plane of `tri` (n,3,3).

    Same filter as the former per-pair code: exact comparison on axis-aligned
    planes, otherwise the determinant with the error bound sum|terms|*eps*16.
    Points equal to a triangle vertex are exactly on the plane. Entries the
    filter cannot decide are `_UNKNOWN`.
    """
    with np.errstate(all="ignore"):
        t0 = tri[:, 0, :]
        a, b = tri[:, 1, :] - t0, tri[:, 2, :] - t0
        c = pts - t0[:, None, :]
        a0, a1, a2 = (a[:, k, None] for k in range(3))
        b0, b1, b2 = (b[:, k, None] for k in range(3))
        c0, c1, c2 = (c[:, :, k] for k in range(3))
        terms = (
            a0 * b1 * c2,
            a1 * b2 * c0,
            a2 * b0 * c1,
            -a2 * b1 * c0,
            -a1 * b0 * c2,
            -a0 * b2 * c1,
        )
        value = terms[0] + terms[1] + terms[2] + terms[3] + terms[4] + terms[5]
        error = (
            np.abs(terms[0])
            + np.abs(terms[1])
            + np.abs(terms[2])
            + np.abs(terms[3])
            + np.abs(terms[4])
            + np.abs(terms[5])
        ) * _EPS * 16
        sign = np.where(
            np.abs(value) > error, np.where(value > 0, 1, -1), _UNKNOWN
        ).astype(np.int8)
    rows = np.nonzero(axis >= 0)[0]
    if rows.size:
        coord = pts[rows, :, axis[rows]]
        plane = tri[rows, 0, axis[rows]][:, None]
        sign[rows] = (coord > plane).astype(np.int8) - (coord < plane).astype(np.int8)
    on_vertex = np.zeros(sign.shape, dtype=bool)
    for m in range(3):
        on_vertex |= (pts == tri[:, None, m, :]).all(axis=2)
    sign[on_vertex] = 0
    return sign


def _segment_verdicts(start, end, tri):
    """Per row: 1 proven crossing, 0 proven miss, `_UNKNOWN` needs exact arithmetic."""

    def cross(u, v):
        return np.stack(
            (
                u[:, 1] * v[:, 2] - u[:, 2] * v[:, 1],
                u[:, 2] * v[:, 0] - u[:, 0] * v[:, 2],
                u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0],
            ),
            axis=1,
        )

    def dot(u, v):
        return u[:, 0] * v[:, 0] + u[:, 1] * v[:, 1] + u[:, 2] * v[:, 2]

    with np.errstate(all="ignore"):
        direction = end - start
        edge1, edge2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        offset = start - tri[:, 0]
        h, q = cross(direction, edge2), cross(offset, edge1)
        det = dot(edge1, h)
        numerators = np.stack(
            (dot(offset, h), dot(direction, q), dot(edge2, q)), axis=1
        )
        bound = (64 * _EPS) * np.maximum.reduce(
            [
                np.sqrt(dot(edge1, edge1))
                * np.sqrt(dot(edge2, edge2))
                * np.sqrt(dot(direction, direction)),
                np.abs(numerators).max(axis=1),
                np.full(len(det), np.finfo(float).tiny),
            ]
        )
        decided = np.abs(det) > bound
        u, v, t = numerators[:, 0] / det, numerators[:, 1] / det, numerators[:, 2] / det
        margin = bound / np.abs(det)
        smallest = np.minimum.reduce([u, v, t, 1 - t, 1 - u - v])
    verdict = np.full(len(det), _UNKNOWN, dtype=np.int8)
    verdict[decided & (smallest > margin)] = 1
    verdict[decided & (smallest < -margin)] = 0
    # An endpoint on a triangle vertex gives t exactly 0 or 1: never a strict crossing.
    for k in range(3):
        verdict[(start == tri[:, k]).all(axis=1) | (end == tri[:, k]).all(axis=1)] = 0
    return verdict


class _ExactPredicates:
    """Exact predicates on binary64 vertices using Python ints scaled by one power of two."""

    def __init__(self, vertices):
        self._vertices = vertices
        self._points = {}
        self._shift = None

    def _point(self, index):
        point = self._points.get(index)
        if point is None:
            if self._shift is None:
                nonzero = self._vertices[np.isfinite(self._vertices) & (self._vertices != 0)]
                # x = m * 2**e with m * 2**53 integral, so x * 2**(53 - min e) is integral.
                self._shift = (
                    max(0, 53 - int(np.frexp(nonzero)[1].min())) if nonzero.size else 0
                )
            coords = []
            for x in self._vertices[index]:
                n, d = float(x).as_integer_ratio()  # raises on NaN/inf like Fraction
                coords.append(n << (self._shift - (d.bit_length() - 1)))
            point = self._points[index] = tuple(coords)
        return point

    def side(self, plane, index):
        """Exact sign of the orientation of vertex `index` against triangle ids `plane`."""
        p0, p1, p2 = (self._point(k) for k in plane)
        q = self._point(index)
        a = [x - o for x, o in zip(p1, p0)]
        b = [x - o for x, o in zip(p2, p0)]
        c = [x - o for x, o in zip(q, p0)]
        exact = (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
        return (exact > 0) - (exact < 0)

    def crosses(self, start, end, plane):
        """Exact strict crossing of segment (vertex ids) with triangle ids `plane`."""

        def sub(a, b):
            return tuple(x - y for x, y in zip(a, b))

        def cross(a, b):
            return (
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0],
            )

        def dot(a, b):
            return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

        p0, p1, p2 = (self._point(k) for k in plane)
        origin = self._point(start)
        direction = sub(self._point(end), origin)
        edge1, edge2, offset = sub(p1, p0), sub(p2, p0), sub(origin, p0)
        h, q = cross(direction, edge2), cross(offset, edge1)
        det = dot(edge1, h)
        if not det:
            return False
        un, vn, tn = dot(offset, h), dot(direction, q), dot(edge2, q)
        if det < 0:
            det, un, vn, tn = -det, -un, -vn, -tn
        return 0 < tn < det and un >= 0 and vn >= 0 and un + vn <= det


# Two coplanar faces overlapping by less than (1e-5 m)^2, the default IFC
# geometric precision, cannot be told apart from a rounding artefact.
NUMERICAL_CONTACT_AREA_M2 = 1e-10
# A transversal crossing where each triangle reaches past the other's plane by less
# than the IFC precision is contact noise, not material overlap.
NUMERICAL_PENETRATION_M = 1e-5


# Skip coplanar pairs a float separating-axis test proves cannot overlap. Only used when
# classifying contacts: a pair skipped overlaps by less than COPLANAR_SEPARATION_M, i.e. by
# an area far below NUMERICAL_CONTACT_AREA_M2, so classification is unchanged.
COPLANAR_PREFILTER = True
COPLANAR_SEPARATION_M = 1e-12


def _coplanar_separated(a, b, axes):
    """Boolean per pair: triangles a, b (n,3,3) with 2D axes (n,2) provably do not overlap."""
    pa = np.take_along_axis(a, axes[:, None, :], axis=2)
    pb = np.take_along_axis(b, axes[:, None, :], axis=2)
    separated = np.zeros(len(a), dtype=bool)
    for own, other in ((pa, pb), (pb, pa)):
        u, v = own[:, 1] - own[:, 0], own[:, 2] - own[:, 0]
        orientation = np.sign(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0])
        for k in range(3):
            edge = own[:, (k + 1) % 3] - own[:, k]
            normal = np.stack((-edge[:, 1], edge[:, 0]), axis=1) * orientation[:, None]
            gap = ((other - own[:, k, None, :]) * normal[:, None, :]).sum(axis=2).max(axis=1)
            # gap is scaled by |edge|; compare against the same scaling of the tolerance.
            separated |= gap <= COPLANAR_SEPARATION_M * np.linalg.norm(edge, axis=1)
    return separated


def _penetration_depths(a, b):
    """For triangle arrays (n,3,3): how far b reaches past the plane of a on its shorter side (0 if not crossing)."""
    normal = np.cross(a[:, 1] - a[:, 0], a[:, 2] - a[:, 0])
    length = np.linalg.norm(normal, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        unit = np.where(length[:, None] > 0, normal / length[:, None], 0.0)
    d = ((b - a[:, :1]) * unit[:, None, :]).sum(axis=2)
    high, low = d.max(axis=1), d.min(axis=1)
    return np.where((high > 0) & (low < 0), np.minimum(high, -low), 0.0)


_contact_sink = ContextVar("contact_sink", default=None)


def has_self_intersection(mesh, details=None, classify_contacts=False, contacts=None):
    """Compatibility predicate. Numerical/backend uncertainty raises, never FAILs.

    With classify_contacts, coplanar overlap that cannot hold material on both
    sides is recorded in `contacts` instead of being a witness: faces with opposite
    outward normals (solids touching face to face, `contact`) and same-facing
    overlap below NUMERICAL_CONTACT_AREA_M2 (`numerical_contact`). Same-facing
    overlap above that area, crossings and volume overlap stay witnesses.

    Candidate triangle pairs (R-tree, j > i) are processed in chunks, in the
    same order as the original per-pair loop, so the first witness is unchanged.
    """
    if details is None:
        details = _intersection_witness.get()
    sink = _contact_sink.get()
    if sink is not None and not classify_contacts:
        # Set by self_intersection_evidence, which calls this with the original arity.
        classify_contacts, contacts = True, sink

    def witness(kind, **values):
        if details is not None:
            details.update(kind=kind, **values)
        return True

    tm = as_trimesh(mesh)
    triangles = tm.triangles
    tree = tm.triangles_tree
    face_ids = np.asarray(mesh.faces).tolist()
    boxes = np.hstack((triangles.min(axis=1), triangles.max(axis=1)))
    flat_axis = _first_flat_axis(triangles)
    exact = _ExactPredicates(tm.vertices)
    # The two axes kept when a triangle is projected onto its own plane (dropping the dominant normal axis).
    drop_axis = np.abs(
        safe_unit_normals(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]))
    ).argmax(axis=1)
    plane_axes = np.array([[a for a in range(3) if a != d] for d in range(3)])[drop_axis]

    def resolve(group, plane, points):
        for m, x in enumerate(group):
            if x == _UNKNOWN:
                group[m] = exact.side(plane, points[m])

    def rejects(group):
        return all(x == 1 for x in group) or all(x == -1 for x in group)

    def scan(first, second):
        first, second = np.asarray(first), np.asarray(second)
        ti, tj = triangles[first], triangles[second]
        sides = _plane_sides(ti, tj, flat_axis[first])
        reverse = _plane_sides(tj, ti, flat_axis[second])
        rejected = (
            (sides == 1).all(1)
            | (sides == -1).all(1)
            | (reverse == 1).all(1)
            | (reverse == -1).all(1)
        )
        keep = np.nonzero(~rejected)[0]
        if not keep.size:
            return False
        events = []  # (coplanar, i, j, row of segment verdicts)
        for s, r, i, j in zip(
            sides[keep].tolist(),
            reverse[keep].tolist(),
            first[keep].tolist(),
            second[keep].tolist(),
        ):
            fi, fj = face_ids[i], face_ids[j]
            shared = len(set(fi) & set(fj)) >= 2
            if shared and any(x not in (0, _UNKNOWN) for x in s):
                continue  # distinct planes with a shared edge meet on that edge only
            # Resolve undecided entries only while the group can still reject.
            for group, plane, points in ((s, fi, fj), (r, fj, fi)):
                if _UNKNOWN in group and (
                    all(x in (1, _UNKNOWN) for x in group)
                    or all(x in (-1, _UNKNOWN) for x in group)
                ):
                    resolve(group, plane, points)
            if rejects(s) or rejects(r):
                continue
            if all(x in (0, _UNKNOWN) for x in s):
                for m, x in enumerate(s):
                    if x == _UNKNOWN:
                        s[m] = exact.side(fi, fj[m])
                        if s[m]:
                            break
            nonzero = any(x not in (0, _UNKNOWN) for x in s)
            if shared and nonzero:
                continue
            events.append((not nonzero, i, j))
        if classify_contacts and COPLANAR_PREFILTER and any(e[0] for e in events):
            flat = [k for k, e in enumerate(events) if e[0]]
            ii = np.array([events[k][1] for k in flat])
            jj = np.array([events[k][2] for k in flat])
            drop = _coplanar_separated(triangles[ii], triangles[jj], plane_axes[ii])
            skipped = {flat[k] for k in np.nonzero(drop)[0]}
            events = [e for k, e in enumerate(events) if k not in skipped]
        crossing = [(i, j) for coplanar, i, j in events if not coplanar]
        verdicts = iter(())
        if crossing:
            a = triangles[[i for i, _ in crossing]]
            b = triangles[[j for _, j in crossing]]
            starts = np.empty((len(crossing), 6, 3))
            ends = np.empty_like(starts)
            planes = np.empty((len(crossing), 6, 3, 3))
            for e, (p, q) in enumerate(_EDGES):
                starts[:, 2 * e], ends[:, 2 * e], planes[:, 2 * e] = a[:, p], a[:, q], b
                starts[:, 2 * e + 1], ends[:, 2 * e + 1], planes[:, 2 * e + 1] = (
                    b[:, p],
                    b[:, q],
                    a,
                )
            verdicts = iter(
                _segment_verdicts(
                    starts.reshape(-1, 3), ends.reshape(-1, 3), planes.reshape(-1, 3, 3)
                )
                .reshape(-1, 6)
                .tolist()
            )
        depths = iter(())
        if classify_contacts and crossing:
            # The smaller of the two reaches is the real overlap: a big triangle always spans both
            # sides of a small one's plane, so the larger value says nothing about contact.
            depths = iter(np.minimum(_penetration_depths(a, b), _penetration_depths(b, a)).tolist())
        for coplanar, i, j in events:
            tri, other = triangles[i], triangles[j]
            if coplanar:
                from shapely.geometry import Polygon

                axes = plane_axes[i].tolist()
                area = Polygon(tri[:, axes]).intersection(Polygon(other[:, axes])).area
                if area > 0 and classify_contacts:
                    facing = float(
                        np.dot(
                            np.cross(tri[1] - tri[0], tri[2] - tri[0]),
                            np.cross(other[1] - other[0], other[2] - other[0]),
                        )
                    )
                    kind = "contact" if facing < 0 else "numerical_contact" if area < NUMERICAL_CONTACT_AREA_M2 else None
                    if kind:
                        if contacts is not None:
                            entry = contacts.setdefault(kind, {"face_pairs": 0, "area_m2": 0.0})
                            entry["face_pairs"] += 1
                            entry["area_m2"] += float(area)
                        continue
                if area > 0:
                    return witness(
                        "COPLANAR_FACE_OVERLAP",
                        triangles=[int(i), int(j)],
                        projected_area_m2=float(area),
                    )
                # Exact coplanarity and zero projected area prove no interior
                # overlap. Segment/triangle ratios are singular on this plane.
                continue
            row = next(verdicts)
            depth = next(depths, None)
            fi, fj = face_ids[i], face_ids[j]
            crossed = False
            for e, (p, q) in enumerate(_EDGES):
                for w, (own, plane) in enumerate(((fi, fj), (fj, fi))):
                    hit = row[2 * e + w]
                    if hit == _UNKNOWN:
                        hit = exact.crosses(own[p], own[q], plane)
                    if hit:
                        crossed = True
                        break
                if crossed:
                    break
            if crossed:
                if depth is not None and depth < NUMERICAL_PENETRATION_M:
                    if contacts is not None:
                        entry = contacts.setdefault("numerical_contact", {"face_pairs": 0, "area_m2": 0.0})
                        entry["face_pairs"] += 1
                    continue
                return witness("TRIANGLE_CROSSING", triangles=[int(i), int(j)])
        return False

    first, second = [], []
    for i in range(len(triangles)):
        for j in tree.intersection(boxes[i]):
            if j > i:
                first.append(i)
                second.append(j)
        if len(first) >= _PAIR_CHUNK:
            if scan(first, second):
                return True
            first, second = [], []
    if first and scan(first, second):
        return True
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
                    volume = mesh_volume(solid_boolean([component, other], "intersection"))
                    if volume > 0:
                        return witness("COMPONENT_VOLUME_OVERLAP", components=[i, j], volume_m3=float(volume))
    return False


def _mesh_key(mesh, kind):
    """Digest of the complete mesh bytes, or None for inputs that cannot be hashed."""
    try:
        vertices = np.asarray(mesh.vertices, dtype="<f8")
        faces = np.asarray(mesh.faces, dtype="<i8")
    except (ValueError, TypeError, OverflowError):
        return None  # Invalid inputs are computed every time.
    digest = hashlib.sha256()
    digest.update(str((vertices.shape, faces.shape)).encode("ascii"))
    digest.update(vertices.tobytes())
    digest.update(faces.tobytes())
    return (kind, digest.digest())


def _cache_store(cache, key, value):
    if len(cache) >= 4096:
        cache.pop(next(iter(cache)))
    cache[key] = value


_accepted_defects = ContextVar("accepted_source_defects", default=None)


def mesh_digest(mesh):
    """SHA-256 (hex) of the complete mesh bytes; binds a review to one exact mesh."""
    key = _mesh_key(mesh, "self-intersection")
    return key[1].hex() if key else None


@contextmanager
def accepted_source_defects(accepted):
    """Waive reviewed defects: {mesh_digest: {"defect": witness kind, "review": {...}}}."""
    token = _accepted_defects.set(dict(accepted))
    try:
        yield
    finally:
        _accepted_defects.reset(token)


def self_intersection_evidence(mesh):
    """Three-way evidence consumed by the independent validator.

    A CONFIRMED defect becomes ACCEPTED_DEFECT only when a reviewer accepted this
    exact mesh (by digest) for this exact witness kind; anything else is unchanged.
    """
    result = _raw_self_intersection_evidence(mesh)
    accepted = _accepted_defects.get()
    if accepted and result["status"] == "CONFIRMED":
        digest = mesh_digest(mesh)
        rule = accepted.get(digest)
        if rule and rule.get("defect") == result.get("witness", {}).get("kind"):
            return {**result, "status": "ACCEPTED_DEFECT", "mesh_sha256": digest, "review": rule.get("review")}
    return result


def prefetch_self_intersection(meshes, min_faces=2000, workers=None):
    """Compute evidence for several heavy meshes in worker processes and store it in the scope cache.

    The evidence is a pure function of the mesh bytes, so the cached results equal what
    sequential calls would produce. Does nothing outside mesh_evidence_scope(), when fewer than
    two heavy meshes need work, or if worker processes cannot be used (callers then compute
    sequentially as before).
    """
    cache = _intersection_evidence.get()
    if cache is None:
        return
    todo, seen = [], set()
    for mesh in meshes:
        if len(mesh.faces) < min_faces:
            continue
        key = _mesh_key(mesh, "self-intersection")
        if key is None or key in cache or key in seen:
            continue
        seen.add(key)
        todo.append((key, mesh))
    if len(todo) < 2:
        return
    import os
    from concurrent.futures import ProcessPoolExecutor

    count = min(len(todo), workers or max(1, (os.cpu_count() or 2) - 1), 8)
    try:
        with ProcessPoolExecutor(max_workers=count) as pool:
            for (key, _), result in zip(todo, pool.map(_raw_self_intersection_evidence, [m for _, m in todo])):
                if result["status"] != "UNCERTAIN":
                    _cache_store(cache, key, deepcopy(result))
    except Exception:  # pragma: no cover - environment without usable process pools
        return


def _raw_self_intersection_evidence(mesh):
    cache = _intersection_evidence.get()
    key = None if cache is None else _mesh_key(mesh, "self-intersection")
    if key is not None and key in cache:
        return deepcopy(cache[key])
    details, contacts = {}, {}
    token = _intersection_witness.set(details)
    sink_token = _contact_sink.set(contacts)
    try:
        hit = has_self_intersection(mesh)
        result = {
            "status": "CONFIRMED" if hit else "CLEAN",
            "method": "adaptive-exact-plane/triangle-crossing/manifold-components-v2",
        }
        if details:
            result["witness"] = details
        if not hit:
            result.update(contacts)
    except Exception as exc:
        result = {"status": "UNCERTAIN", "reason": str(exc)}
    finally:
        _contact_sink.reset(sink_token)
        _intersection_witness.reset(token)
    if key is not None and result["status"] != "UNCERTAIN":
        _cache_store(cache, key, deepcopy(result))
    return result
