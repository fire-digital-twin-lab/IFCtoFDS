"""Exact decomposition of a rectilinear solid into axis-aligned boxes.

A wall with window or door openings is rectilinear but not a box, so it used to be exported as
a GEOM cut-cell surface. FDS handles plain &OBST boxes better (no cut-cell geometry), and a set of
boxes can be proven equal to the source solid. Returns None unless the cover is exact.
"""

import os

import numpy as np

from .component_union import winding_numbers
from .mesh import as_trimesh, mesh_digest, mesh_volume

AXIS_TOLERANCE = 1e-9
MAX_BOXES = 64  # more boxes than this is no better than a cut-cell surface
MAX_WORK = 5e7  # cells x faces handled by the winding-number classification


def _planes(values):
    """Distinct plane coordinates; values within AXIS_TOLERANCE are one plane (median of the cluster)."""
    ordered = np.sort(values)
    breaks = np.nonzero(np.diff(ordered) > AXIS_TOLERANCE)[0] + 1
    return np.array([np.median(c) for c in np.split(ordered, breaks)])


_cache = {}


def box_sets_enabled():
    """Opt-in (IFCFDS_OBST_BOX_SETS=1): the air_path gate's Boolean is unreliable on touching boxes,
    so a proven cover can still flip its verdict. Enable once that gate is fixed (plan M2.5)."""
    return os.environ.get("IFCFDS_OBST_BOX_SETS") == "1"


def is_obstruction_box_set(mesh):
    """True when the solid decomposes exactly into boxes. Memoised: policy, exporter and plan check call it."""
    boxes = box_set_for(mesh)
    return boxes is not None and len(boxes) <= MAX_BOXES


def box_set_for(mesh):
    key = mesh_digest(mesh)
    if key not in _cache:
        if len(_cache) >= 2048:
            _cache.pop(next(iter(_cache)))
        _cache[key] = rectilinear_boxes(mesh)
    return _cache[key]


def rectilinear_boxes(mesh, max_cells=200_000):
    """[(xmin, xmax, ymin, ymax, zmin, zmax), ...] covering the solid exactly, or None."""
    tm = as_trimesh(mesh)
    if not len(tm.faces) or not np.all(np.abs(tm.face_normals).max(axis=1) > 1 - AXIS_TOLERANCE):
        return None
    if len(tm.split(only_watertight=False, repair=False)) != 1:
        return None  # touching components (frame + glass) would lose their shells and shared faces
    grid = [_planes(tm.vertices[:, axis]) for axis in range(3)]
    shape = tuple(len(g) - 1 for g in grid)
    cells = int(np.prod(shape))
    if min(shape) < 1 or cells > max_cells or cells * len(tm.faces) > MAX_WORK:
        return None
    centres = np.stack(np.meshgrid(*[(g[:-1] + g[1:]) / 2 for g in grid], indexing="ij"), axis=-1).reshape(-1, 3)
    occupied = (winding_numbers(tm, centres) > 0.5).reshape(shape)
    boxes, taken = [], np.zeros(shape, dtype=bool)
    for i, j, k in zip(*np.nonzero(occupied)):
        if taken[i, j, k]:
            continue
        free = occupied & ~taken
        i2 = i
        while i2 + 1 < shape[0] and free[i2 + 1, j, k]:
            i2 += 1
        j2 = j
        while j2 + 1 < shape[1] and free[i : i2 + 1, j2 + 1, k].all():
            j2 += 1
        k2 = k
        while k2 + 1 < shape[2] and free[i : i2 + 1, j : j2 + 1, k2 + 1].all():
            k2 += 1
        taken[i : i2 + 1, j : j2 + 1, k : k2 + 1] = True
        boxes.append((grid[0][i], grid[0][i2 + 1], grid[1][j], grid[1][j2 + 1], grid[2][k], grid[2][k2 + 1]))
    volume = sum((b[1] - b[0]) * (b[3] - b[2]) * (b[5] - b[4]) for b in boxes)
    if not boxes or abs(volume - mesh_volume(tm)) > 1e-9 * max(1.0, volume):
        return None  # the cell classification did not reproduce the solid
    boxes = [tuple(float(x) for x in b) for b in boxes]
    return boxes if _cover_is_proven(mesh, boxes) else None


def _cover_is_proven(mesh, boxes):
    """Accept a cover only when the audit's own comparison would: same surface, same shell count."""
    from ifc_to_fds.core.canonical import BoundingBox  # local: geometry must not import validation at load time
    from ifc_to_fds.validation.metrics import compare_solids

    from .mesh import box_mesh

    pieces = [box_mesh(BoundingBox(xmin=b[0], xmax=b[1], ymin=b[2], ymax=b[3], zmin=b[4], zmax=b[5])) for b in boxes]
    try:
        m = compare_solids(mesh, pieces)
    except (ValueError, RuntimeError):
        return False
    return bool(
        m["surface_proven"]
        and m["solid_iou"] > 1 - 1e-9
        and m["relative_volume_error"] < 1e-9
        and m["reference_components"] == m["output_components"]
    )
