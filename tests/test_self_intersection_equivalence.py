"""Equivalence of the vectorized has_self_intersection against the original.

`_old_has_self_intersection` is a verbatim copy of the pre-rewrite function
(commit e3d8592, ifc_to_fds/geometry/mesh.py) used as the oracle: same bool,
same witness kind and same witness triangle indices are required.
"""

import random
from fractions import Fraction  # used by the verbatim oracle below
from pathlib import Path

import numpy as np
import pytest
import trimesh

from ifc_to_fds.core.canonical import TriangleMesh
from ifc_to_fds.geometry.boolean import solid_boolean
from ifc_to_fds.geometry.mesh import (
    _intersection_witness,
    as_trimesh,
    has_self_intersection,
    safe_unit_normals,
)

ROOT = Path(__file__).resolve().parents[1]


def run(function, mesh):
    details = {}
    try:
        hit = function(mesh, details)
    except Exception as exc:  # both versions must fail the same way
        return ("raise", type(exc).__name__, None)
    return (hit, details.get("kind"), details)


def assert_equivalent(mesh, label=""):
    old, new = run(_old_has_self_intersection, mesh), run(has_self_intersection, mesh)
    assert new[:2] == old[:2], (label, old, new)
    assert new[2] == old[2], (label, old, new)  # witness triangles / components / areas
    return old[0]


def merge(parts):
    vertices, faces = [], []
    for part in parts:
        faces += (np.asarray(part.faces) + len(vertices)).tolist()
        vertices += np.asarray(part.vertices).tolist()
    return TriangleMesh(vertices=vertices, faces=faces)


def box(lo, size):
    b = trimesh.creation.box(extents=size)
    b.apply_translation(np.asarray(lo, float) + np.asarray(size, float) / 2)
    return b


def box_pair_meshes():
    """Touching/crossing/nested/shared edge-vertex/coplanar boxes with perturbations."""
    rng = random.Random(7)
    unit = [1.0, 1.0, 1.0]
    offsets = [
        (1, 0, 0), (0.5, 0, 0), (1, 1, 0), (1, 1, 1), (0.25, 0.25, 0.25),
        (0, 0, 1), (1, 0.5, 0.5), (0.5, 0.5, 0.5), (2, 0, 0), (0.999, 0, 0),
    ]
    cases = []
    for off in offsets:
        for eps in (0.0, 1e-9, -1e-9, 1e-12, -1e-12):
            for base in (0.0, 6e5):
                a = box((base, base, 0.0), unit)
                b = box(
                    (base + off[0] + eps, base + off[1], off[2] - eps), unit
                )
                cases.append((f"box off={off} eps={eps} base={base}", merge([a, b])))
    # nested boxes (cavity-like and containing)
    outer, inner = box((0, 0, 0), [4, 4, 4]), box((1, 1, 1), [1, 1, 1])
    cases.append(("nested", merge([outer, inner])))
    cases.append(("nested+off", merge([box((6e5, 6e5, 0), [4, 4, 4]), box((6e5 + 1, 6e5 + 1, 1), [1, 1, 1])])))
    # coplanar overlapping squares
    sq = lambda x: TriangleMesh(
        vertices=[[x, 0, 0], [x + 1, 0, 0], [x + 1, 1, 0], [x, 1, 0]],
        faces=[[0, 1, 2], [0, 2, 3]],
    )
    cases.append(("coplanar overlap", merge([sq(0), sq(0.5)])))
    cases.append(("coplanar touching", merge([sq(0), sq(1.0)])))
    cases.append(("coplanar 1e-9 gap", merge([sq(0), sq(1.0 + 1e-9)])))
    # single boxes and random rotated boxes
    cases.append(("single box", merge([box((0, 0, 0), unit)])))
    for k in range(25):
        parts = []
        for _ in range(rng.randint(2, 3)):
            c = [rng.uniform(0, 2) for _ in range(3)]
            e = [rng.uniform(0.3, 1.5) for _ in range(3)]
            part = box((0, 0, 0), e)
            part.apply_transform(
                trimesh.transformations.random_rotation_matrix(
                    np.random.RandomState(rng.randint(0, 10**6)).rand(3)
                )
            )
            part.apply_translation(c)
            parts.append(part)
        cases.append((f"random boxes {k}", merge(parts)))
    return cases


def soup_meshes():
    """Triangle soups on a tiny integer grid (dense degeneracy) and random floats."""
    rng = random.Random(11)
    cases = []
    for k in range(250):
        grid = rng.choice([2, 3, 4])
        n = rng.randint(2, 8)
        vertices = [[float(rng.randint(0, grid)) for _ in range(3)] for _ in range(12)]
        if k % 3 == 1:  # tiny perturbations
            vertices = [[x + rng.choice([0, 1e-9, -1e-12]) for x in v] for v in vertices]
        if k % 5 == 2:  # large offset
            vertices = [[x + 6e5 for x in v] for v in vertices]
        faces = [rng.sample(range(len(vertices)), 3) for _ in range(n)]
        cases.append((f"grid soup {k}", TriangleMesh(vertices=vertices, faces=faces)))
    for k in range(120):
        n = rng.randint(2, 10)
        vertices = [[rng.uniform(0, 1) for _ in range(3)] for _ in range(3 * n)]
        faces = [[3 * i, 3 * i + 1, 3 * i + 2] for i in range(n)]
        cases.append((f"float soup {k}", TriangleMesh(vertices=vertices, faces=faces)))
    return cases


@pytest.mark.parametrize("group", [box_pair_meshes, soup_meshes])
def test_random_meshes_match_oracle(group):
    verdicts = [assert_equivalent(mesh, label) for label, mesh in group()]
    # The generators must exercise both outcomes, else the comparison is vacuous.
    assert any(v is True for v in verdicts) and any(v is False for v in verdicts)


def _fzk_meshes():
    import ifc_to_fds.fire  # noqa: F401  (registers the geometry backend)
    from ifc_to_fds.application.services.model_preparer import prepare_model

    path = ROOT / "examples" / "AC20-FZK-Haus.ifc"
    if not path.exists():
        pytest.skip("AC20-FZK-Haus.ifc not available")
    model = prepare_model([str(path)], {}, reference=True)
    return [e.mesh for e in model.elements if getattr(e, "mesh", None) is not None]


@pytest.mark.slow
def test_fzk_haus_every_solid_matches_oracle():
    meshes = _fzk_meshes()
    assert len(meshes) > 50
    verdicts = [assert_equivalent(mesh, f"FZK element {i}") for i, mesh in enumerate(meshes)]
    assert len(verdicts) == len(meshes)


# ---- verbatim oracle (commit e3d8592) ----
def _old_has_self_intersection(mesh, details=None):
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
            normal = safe_unit_normals(np.cross(tri[1] - tri[0], tri[2] - tri[0]))
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
