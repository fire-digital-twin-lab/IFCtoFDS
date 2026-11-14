"""Fuse overlapping sub-solids of one IFC product into the region they occupy.

IFC products are often built from several representation items that overlap
(window frame and glazing, railing bars). The product occupies their union; the
overlap is not a defect of any single solid. A fused mesh is accepted only with
evidence that does not rely on the Boolean kernel that produced it:

- every component is a closed volume,
- the result is a valid, self-intersection-free solid,
- max(V_i) <= V(union) <= sum(V_i),
- a point-sampling oracle (generalized winding number, not Manifold) agrees on
  inside/outside for the union and for "inside any component".

Any failed check returns the source mesh unchanged, so the element stays blocked.
"""

import hashlib

import numpy as np

from ifc_to_fds.domain.bim import TriangleMesh

from .boolean import solid_boolean
from .mesh import as_trimesh, mesh_digest, mesh_volume, self_intersection_evidence, valid_solid

# Part of the converter geometry cache key: change it whenever fusing results can change.
UNION_METHOD = "manifold-union+winding-number-oracle-v1"
ORACLE_SAMPLES = 1024
# Sample points this close to a surface can legitimately disagree between two
# triangulations of the same boundary; they are reported, not counted.
ORACLE_BOUNDARY_M = 1e-6
VOLUME_TOLERANCE = 1e-9


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


def winding_numbers(tm, points, chunk=128):
    """Generalized winding number of each point (Jacobson et al. 2013): ~1 inside, ~0 outside.

    Deterministic and robust to coincident or overlapping faces, unlike ray parity.
    """
    triangles = tm.triangles
    result = np.empty(len(points))
    for start in range(0, len(points), chunk):
        p = points[start : start + chunk, None, None, :]
        a, b, c = (triangles[None, :, k, :] - p[:, :, 0, :] for k in range(3))
        la, lb, lc = (np.linalg.norm(v, axis=-1) for v in (a, b, c))
        numerator = np.einsum("pfk,pfk->pf", a, np.cross(b, c))
        denominator = (
            la * lb * lc
            + np.einsum("pfk,pfk->pf", a, b) * lc
            + np.einsum("pfk,pfk->pf", a, c) * lb
            + np.einsum("pfk,pfk->pf", b, c) * la
        )
        result[start : start + chunk] = (2.0 * np.arctan2(numerator, denominator)).sum(axis=1) / (4 * np.pi)
    return result


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
    in_union = winding_numbers(fused, points) > 0.5
    in_any = np.zeros(len(points), dtype=bool)
    for component in components:
        in_any |= winding_numbers(component, points) > 0.5
    disagree = np.nonzero(in_union != in_any)[0]
    near = 0
    if len(disagree):
        from trimesh.proximity import closest_point

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
    evidence = self_intersection_evidence(mesh)
    if evidence["status"] != "CONFIRMED":
        return mesh, None

    def refuse(reason, **extra):
        return mesh, dict(status="NOT_APPLIED", reason=reason, components=len(components),
                          witness=evidence.get("witness"), **extra)

    for index, component in enumerate(components):
        if not component.is_volume:
            return refuse(f"component {index} is not a closed volume")
    volumes = [mesh_volume(c) for c in components]
    try:
        fused_tm = solid_boolean(components, "union")
    except Exception as exc:  # kernel failure keeps the source and its finding
        return refuse(f"union failed: {exc}")
    fused = _mesh(fused_tm)
    if not valid_solid(fused):
        return refuse("union is not a valid closed solid")
    if self_intersection_evidence(fused)["status"] != "CLEAN":
        return refuse("union is still self-intersecting")
    union_volume = mesh_volume(fused_tm)
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
        witness=evidence.get("witness"),
        source_mesh_sha256=digest,
        component_volumes_m3=volumes,
        union_volume_m3=union_volume,
        oracle=oracle,
    )
