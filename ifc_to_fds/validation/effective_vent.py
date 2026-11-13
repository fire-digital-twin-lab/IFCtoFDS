"""Đối chiếu ô thoáng OPEN ngoài biên một lưới FDS 6.11.1."""

import math

import numpy as np

from .acceptance import GateResult, GateStatus
from .smv import grid_bounds, table_start


def _face_axis_and_orientation(indices, grids):
    flat = [i for i in (0, 2, 4) if indices[i] == indices[i + 1]]
    if len(flat) != 1:
        raise ValueError("Expected one noncollapsed rectangular VENT face")
    i = flat[0]
    if indices[i] == 0:
        return i, i // 2 + 1
    if indices[i] == len(grids[i // 2]) - 1:
        return i, -(i // 2 + 1)
    raise ValueError("VENT does not lie on the exterior mesh face")


def _expected_face(vent, grids, domain):
    xb = vent.values["XB"]
    if len(xb) != 6 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in xb):
        raise ValueError(f"VENT requires six numeric coordinates: {vent.id}")
    flat = [i for i in (0, 2, 4) if xb[i] == xb[i + 1]]
    if len(flat) != 1 or any(xb[i] > xb[i + 1] for i in (0, 2, 4)):
        raise ValueError(f"VENT requires a positive-area planar rectangle: {vent.id}")
    normal = flat[0]
    if xb[normal] not in (domain[normal], domain[normal + 1]):
        raise ValueError(f"VENT requires an exterior mesh face: {vent.id}")
    indices = []
    for i, x in enumerate(xb):
        grid = grids[i // 2]
        lo = i - i % 2
        if not domain[lo] <= x <= domain[lo + 1]:
            raise ValueError(f"VENT lies outside its mesh: {vent.id}")
        distances = np.abs(np.asarray(grid) - x)
        nearest = np.flatnonzero(distances <= distances.min() + 1e-8)
        if len(nearest) != 1:
            raise ValueError(f"Unproved half-cell VENT rounding tie: {vent.id}")
        indices.append(int(nearest[0]))
    return normal, indices


def _original_vents(lines):
    start = table_start(lines, "VENTORIG")
    count = int(lines[start])
    if count < 0 or start + count >= len(lines):
        raise ValueError("Invalid SMV VENTORIG count")
    original = {}
    for line in lines[start + 1 : start + 1 + count]:
        text, marker, label = line.partition("!")
        bounds = [float(x) for x in text.split()]
        label = label.strip()
        if not marker or not label or label in original or len(bounds) != 6 or not np.isfinite(bounds).all():
            raise ValueError("Ambiguous SMV VENTORIG identity")
        original[label] = bounds
    return original


def _open_faces(lines, grids):
    if int(lines[table_start(lines, "CVENT")]) != 0:
        raise ValueError("Circular SMV vents are outside the reviewed subset")
    start = table_start(lines, "VENT")
    count, dummy = (int(x) for x in lines[start].split())
    start += 1
    if not 0 <= dummy <= count or start + 2 * count > len(lines):
        raise ValueError("Invalid SMV VENT counts")
    faces = []
    for i in range(count):
        fields = lines[start + i].split()
        if len(fields) < 8 or int(fields[6]) != i + 1:
            raise ValueError("Invalid SMV VENT row order")
        text, marker, direction = lines[start + count + i].partition("!")
        tokens = text.split()
        if len(tokens) < 8:
            raise ValueError("Incomplete SMV VENT index row")
        indices = [int(v) for v in tokens[:6]]
        grid_bounds(indices, grids)
        kind = int(tokens[7])
        if i >= count - dummy:
            if kind != 0 or marker:
                raise ValueError("Unexpected boundary condition on a dummy SMV VENT")
            continue
        bounds = [float(v) for v in fields[:6]]
        if not marker or not np.isfinite(bounds).all():
            raise ValueError("Missing SMV VENT orientation or coordinates")
        faces.append((bounds, indices, kind, int(direction)))
    return faces


def _blocked_rectangles(indices, normal, orientation, obstructions):
    tangent = [i for i in (0, 2, 4) if i != normal]
    slab_start = indices[normal] - int(orientation < 0)
    blocked = []
    for _, solid in obstructions:
        if solid[normal] > slab_start or solid[normal + 1] < slab_start + 1:
            continue
        patch = [
            value for i in tangent for value in (
                max(indices[i], solid[i]), min(indices[i + 1], solid[i + 1])
            )
        ]
        if patch[0] < patch[1] and patch[2] < patch[3]:
            blocked.append(patch)
    return tangent, blocked


def _blocked_area(rectangles, grids):
    """Đo hợp các hình chữ nhật theo dải để đếm phần giao đúng một lần."""
    cuts = sorted({x for rectangle in rectangles for x in rectangle[:2]})
    cells, areas = 0, []
    gx, gy = grids
    for left, right in zip(cuts, cuts[1:]):
        intervals = sorted((y0, y1) for x0, x1, y0, y1 in rectangles if x0 <= left < x1)
        top = 0
        for lo, hi in intervals:
            bottom = max(top, lo)
            if hi > bottom:
                cells += (right - left) * (hi - bottom)
                areas.append((gx[right] - gx[left]) * (gy[hi] - gy[bottom]))
                top = hi
    return cells, math.fsum(areas)


def verify_open_vents(mesh, vents, lines, grid_data, evidence):
    grids, obstructions = grid_data
    try:
        expected = {vent.id: _expected_face(vent, grids, mesh.values["XB"]) for vent in vents}
        originals = _original_vents(lines)
        faces = _open_faces(lines, grids)
    except (ValueError, IndexError) as exc:
        return GateResult(status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence)

    if set(originals) != set(expected) or any(
        not np.allclose(originals[vent.id], vent.values["XB"], atol=5.1e-6, rtol=0)
        for vent in vents
    ):
        return GateResult(status=GateStatus.FAIL, reason="Solver VENT inventory differs from input", evidence=evidence)

    measured = evidence["open_vents"] = {}
    accepted_faces = []
    for vent in vents:
        normal, indices = expected[vent.id]
        if sum(indices[i] == indices[i + 1] for i in (0, 2, 4)) != 1:
            return GateResult(status=GateStatus.FAIL, reason=f"OPEN VENT collapsed on FDS mesh: {vent.id}", evidence=evidence)
        matches = [i for i, (xb, _, _, _) in enumerate(faces) if xb == originals[vent.id]]
        if len(matches) != 1:
            return GateResult(status=GateStatus.FAIL, reason=f"OPEN VENT has no unique effective face: {vent.id}", evidence=evidence)
        _, actual, kind, ior = faces.pop(matches[0])
        _, orientation = _face_axis_and_orientation(indices, grids)
        if actual != indices or kind != 2 or ior != orientation:
            return GateResult(status=GateStatus.FAIL, reason=f"OPEN VENT indices, boundary type or orientation differ: {vent.id}", evidence=evidence)
        tangent, blocked = _blocked_rectangles(actual, normal, ior, obstructions)
        if any(
            other[normal] == actual[normal] == other[normal + 1]
            and all(max(actual[i], other[i]) < min(actual[i + 1], other[i + 1]) for i in tangent)
            for other in accepted_faces
        ):
            return GateResult(status=GateStatus.INCONCLUSIVE, reason=f"Overlapping OPEN VENT faces: {vent.id}", evidence=evidence)
        accepted_faces.append(actual)
        bounds = grid_bounds(actual, grids)
        face_cells = math.prod(actual[i + 1] - actual[i] for i in tangent)
        area = math.prod(bounds[i + 1] - bounds[i] for i in tangent)
        blocked_cells, blocked_area = _blocked_area(blocked, [grids[i // 2] for i in tangent])
        measured[vent.id] = dict(
            indices=actual, bounds_m=bounds, orientation=ior, face_cells=face_cells,
            area_m2=area, blocked_face_cells=blocked_cells,
            open_area_m2=max(0.0, area - blocked_area),
            deck_area_m2=math.prod(vent.values["XB"][i + 1] - vent.values["XB"][i] for i in tangent),
        )
        if blocked_cells:
            return GateResult(status=GateStatus.FAIL, reason=f"OPEN VENT faces obstructed by solver OBST: {vent.id}", evidence=evidence)
    if faces:
        return GateResult(status=GateStatus.FAIL, reason="Unexpected effective SMV VENT rows", evidence=evidence)
    return GateResult(status=GateStatus.PASS, reason="Static exterior OPEN VENT faces and OBST occupancy verified", evidence=evidence)
