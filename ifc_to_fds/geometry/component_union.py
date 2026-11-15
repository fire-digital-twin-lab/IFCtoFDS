"""Fuse overlapping sub-solids of one IFC product into the region they occupy.

IFC products are often built from several representation items that overlap
(window frame and glazing, railing bars). The product occupies their union; the
overlap is not a defect of any single solid. A fused mesh is accepted only with
evidence that does not rely on the Boolean kernel that produced it:

- every component is a closed volume,
- the result is a valid closed solid (Manifold output is intersection-free by construction;
  the audit's source-topology preflight still scans it exactly and blocks a defect),
- max(V_i) <= V(union) <= sum(V_i),
- a point-sampling oracle (generalized winding number, not Manifold) agrees on
  inside/outside for the union and for "inside any component".

Any failed check returns the source mesh unchanged, so the element stays blocked.
"""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from trimesh.proximity import closest_point

from ifc_to_fds.domain.bim import TriangleMesh

from .boolean import solid_boolean
from .mesh import as_trimesh, mesh_digest, mesh_volume, self_intersection_evidence, valid_solid

# Part of the converter geometry cache key: change it whenever fusing results can change.
UNION_METHOD = "manifold-union+winding-number-oracle-v4"
ORACLE_SAMPLES = 1024
# Sample points this close to a surface can legitimately disagree between two
# triangulations of the same boundary; they are reported, not counted.
ORACLE_BOUNDARY_M = 1e-6
VOLUME_TOLERANCE = 1e-9
BOX_MARGIN_M = 1e-9
SCAN_FACE_LIMIT = 5000


def _mesh(tm):
    return TriangleMesh(vertices=tm.vertices.tolist(), faces=tm.faces.tolist())


def _overlapping_boxes(components):
    """Intersections of component bounding boxes whose interiors overlap."""
    boxes = []
    for i, a in enumerate(components):
        for b in components[i + 1 :]:
            lo = np.maximum(a.bounds[0], b.bounds[0])
            hi = np.minimum(a.bounds[1], b.bounds[1])
            if np.all(hi > lo):
                boxes.append((lo, hi))
    return boxes


PAIRS_PER_CHUNK = 1 << 13  # point x triangle pairs per block; measured optimum (L1/L2-sized arrays), 2-3x faster than 2^20
THREADED_PAIRS = 1 << 22  # below this (about 4,000 triangles for 1,024 points) the thread hand-off costs more than it saves
_WORKERS = min(4, os.cpu_count() or 1)
_pool = None


def _threads():
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="winding")
    return _pool


def winding_numbers(tm, points):
    """Generalized winding number of each point (Jacobson et al. 2013): ~1 inside, ~0 outside.
    Deterministic and robust to coincident or overlapping faces, unlike ray parity.
    Plain elementwise arithmetic on (points x triangles) blocks: several times faster than
    np.cross / einsum on (P, F, 3) arrays, with the same result up to rounding.
    """
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    triangles = np.asarray(tm.triangles, dtype=float)
    result = np.zeros(len(points))
    if not len(points) or not len(triangles):
        return result
    corner = [[triangles[:, k, axis][None, :] for axis in range(3)] for k in range(3)]
    block = max(1, PAIRS_PER_CHUNK // len(triangles))

    def solve(start):
        p = points[start : start + block]
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = (
            [corner[k][axis] - p[:, axis, None] for axis in range(3)] for k in range(3)
        )
        la = np.sqrt(ax * ax + ay * ay + az * az)
        lb = np.sqrt(bx * bx + by * by + bz * bz)
        lc = np.sqrt(cx * cx + cy * cy + cz * cz)
        numerator = ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)
        denominator = (
            la * lb * lc
            + (ax * bx + ay * by + az * bz) * lc
            + (ax * cx + ay * cy + az * cz) * lb
            + (bx * cx + by * cy + bz * cz) * la
        )
        return (2.0 * np.arctan2(numerator, denominator)).sum(axis=1) / (4 * np.pi)

    starts = range(0, len(points), block)
    if len(starts) > 1 and len(points) * len(triangles) >= THREADED_PAIRS and _WORKERS > 1:
        # numpy releases the GIL inside these elementwise operations, so blocks run in parallel.
        for start, values in zip(starts, _threads().map(solve, starts)):
            result[start : start + block] = values
    else:
        for start in starts:
            result[start : start + block] = solve(start)
    return result


def _inside(tm, points):
    """winding > 0.5 for every point, evaluated only where the mesh can contain it.

    A closed mesh has winding number 0 outside its bounding box, so those points are never
    sent through the triangle sum; components are usually small next to the sampled region.
    """
    lo, hi = tm.bounds
    near = np.all((points >= lo - BOX_MARGIN_M) & (points <= hi + BOX_MARGIN_M), axis=1)
    inside = np.zeros(len(points), dtype=bool)
    if near.any():
        inside[near] = winding_numbers(tm, points[near]) > 0.5
    return inside


def _oracle(fused, components, boxes, seed):
    """Half the samples in the overlap regions (where a wrong union would show), half overall."""
    rng = np.random.default_rng(seed)
    lo, hi = fused.bounds
    local = ORACLE_SAMPLES // 2
    picks = rng.integers(0, len(boxes), local)
    box_lo = np.array([boxes[k][0] for k in picks])
    box_hi = np.array([boxes[k][1] for k in picks])
    points = np.vstack(
        (box_lo + rng.random((local, 3)) * (box_hi - box_lo),
         lo + rng.random((ORACLE_SAMPLES - local, 3)) * (hi - lo))
    )
    in_union = _inside(fused, points)
    in_any = np.zeros(len(points), dtype=bool)
    for component in components:
        in_any |= _inside(component, points)
    disagree = np.nonzero(in_union != in_any)[0]
    near = 0
    if len(disagree):
        _, distance, _ = closest_point(fused, points[disagree])
        near = int(np.count_nonzero(distance <= ORACLE_BOUNDARY_M))
    return dict(samples=len(points), inside=int(in_union.sum()), mismatches=len(disagree) - near, near_boundary=near)


def fuse_overlapping_components(mesh):
    """Return (mesh, proof). proof is None when nothing needed fusing."""
    with np.errstate(divide="ignore", invalid="ignore"):  # trimesh mass props of thin parts
        return _fuse(mesh)


def _fuse(mesh):
    if mesh is None or not valid_solid(mesh):
        return mesh, None
    source = as_trimesh(mesh)
    components = source.split(only_watertight=False, repair=False)
    if len(components) < 2:
        return mesh, None
    boxes = _overlapping_boxes(components)
    if not boxes:  # components only touch or are apart: nothing a union could fix
        return mesh, None
    if not all(component.is_volume for component in components):
        return mesh, None
    volumes = [mesh_volume(c) for c in components]
    try:
        fused_tm = solid_boolean(components, "union")
    except (RuntimeError, ValueError):
        return mesh, None  # no usable union: the element keeps its source mesh and finding
    union_volume = mesh_volume(fused_tm)
    overlap = sum(volumes) - union_volume
    if overlap <= VOLUME_TOLERANCE * max(1.0, sum(volumes)):
        # No shared volume, yet the exact scan may still report crossing triangles between
        # touching components (their union is the same body). Scan only meshes light enough to
        # afford it. shortcut: meshes over SCAN_FACE_LIMIT faces keep their source mesh and are
        # judged by the audit's preflight; raise the limit when the scan gets cheaper.
        if len(mesh.faces) > SCAN_FACE_LIMIT or self_intersection_evidence(mesh)["status"] != "CONFIRMED":
            return mesh, None

    def refuse(reason, **extra):
        return mesh, dict(status="NOT_APPLIED", reason=reason, components=len(components),
                          overlap_volume_m3=overlap, **extra)

    fused = _mesh(fused_tm)
    if not valid_solid(fused):
        return refuse("union is not a valid closed solid")
    if not (max(volumes) - VOLUME_TOLERANCE <= union_volume <= sum(volumes) + VOLUME_TOLERANCE):
        return refuse("union volume outside [max component, sum of components]", union_volume_m3=union_volume)
    digest = mesh_digest(mesh)
    oracle = _oracle(fused_tm, components, boxes, int(hashlib.sha256(digest.encode()).hexdigest()[:8], 16))
    if oracle["mismatches"]:
        return refuse("sampling oracle disagrees with the union", oracle=oracle)
    return fused, dict(
        status="APPLIED",
        method=UNION_METHOD,
        components=len(components),
        overlap_volume_m3=overlap,
        source_mesh_sha256=digest,
        component_volumes_m3=volumes,
        union_volume_m3=union_volume,
        oracle=oracle,
    )
