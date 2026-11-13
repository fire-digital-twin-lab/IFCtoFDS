"""Kiểm chứng hình học hiệu dụng từ các bảng chỉ số lưới FDS 6.11.1.

Format reference: firemodels/fds FDS-6.11.1 Source/dump.f90, SMV OBST
section. Physical bounds come from TRNX/Y/Z at the solver's integer indices,
not the original unsnapped coordinates in the first OBST table.
"""

import hashlib
import math
import numpy as np
from ifc_to_fds.geometry.mesh import bounds_for_vertices, is_axis_aligned_box
from .acceptance import GateResult, GateStatus
from .effective_vent import verify_open_vents
from .parser import parse_fds
from .smv import grid_bounds, read_mesh_obstructions


EFFECTIVE_ADAPTER_VERSION = "smv-effective-6.11.1-v3"


def check_opening_grid_alignment(opening_mesh, host_bounds, parsed):
    """Estimate resolution of a rectangular through-opening on one emitted mesh."""
    if host_bounds is None or not is_axis_aligned_box(opening_mesh):
        return {"status": "INCONCLUSIVE", "reason": "Opening is not a proven axis-aligned box"}
    box = bounds_for_vertices(opening_mesh.vertices).to_xb()
    host = host_bounds.to_xb()
    tolerance = 1e-6
    through = [
        axis for axis in range(3)
        if box[2 * axis] <= host[2 * axis] + tolerance
        and box[2 * axis + 1] >= host[2 * axis + 1] - tolerance
    ]
    if len(through) != 1:
        return {"status": "INCONCLUSIVE", "reason": "Host bounds do not identify one through axis"}
    normal = through[0]
    tangents = [axis for axis in range(3) if axis != normal]
    tangent_tolerance = 0.05
    if any(
        box[2 * axis] < host[2 * axis] - tangent_tolerance
        or box[2 * axis + 1] > host[2 * axis + 1] + tangent_tolerance
        for axis in tangents
    ):
        return {"status": "INCONCLUSIVE", "reason": "Opening extends beyond the host cross-section"}
    for axis in tangents:
        box[2 * axis] = max(box[2 * axis], host[2 * axis])
        box[2 * axis + 1] = min(box[2 * axis + 1], host[2 * axis + 1])
    if any(box[2 * axis + 1] <= box[2 * axis] for axis in tangents):
        return {"status": "INCONCLUSIVE", "reason": "Opening does not intersect host cross-section"}
    # Ignore the portion of a through-cut tool protruding outside the host.
    box[2 * normal:2 * normal + 2] = host[2 * normal:2 * normal + 2]
    meshes = [record for record in parsed.records if record.kind == "MESH"]
    covering = [
        (index, record) for index, record in enumerate(meshes)
        if all(record.values["XB"][i] <= box[i] + tolerance
               and record.values["XB"][i + 1] >= box[i + 1] - tolerance for i in (0, 2, 4))
    ]
    if len(covering) != 1:
        return {"status": "INCONCLUSIVE", "reason": "Opening is not contained in one emitted mesh"}

    index, record = covering[0]
    xb, ijk = record.values["XB"], record.values["IJK"]
    spacing = [(xb[i + 1] - xb[i]) / n for i, n in zip((0, 2, 4), ijk)]
    widths = [box[2 * axis + 1] - box[2 * axis] for axis in tangents]
    snapped_cells = []
    for axis in tangents:
        origin = xb[2 * axis]
        step = spacing[axis]
        first = math.floor((box[2 * axis] - origin) / step + 0.5)
        last = math.floor((box[2 * axis + 1] - origin) / step + 0.5)
        snapped_cells.append(last - first)
    return {
        "status": "ESTIMATED",
        "normal_axis": "XYZ"[normal],
        "mesh_id": record.id or str(index + 1),
        "mesh_origin_m": xb[::2],
        "mesh_spacing_m": spacing,
        "clear_spans_m": widths,
        "clear_area_m2": widths[0] * widths[1],
        "snapped_tangential_cells": snapped_cells,
        "risk_sealed_by_grid": min(snapped_cells) == 0 or any(
            width < 2 * spacing[axis] for width, axis in zip(widths, tangents)
        ),
    }


def effective_obstructions(fds_text, smv_text, *, solver_version="6.11.1"):
    parsed = parse_fds(fds_text)
    if parsed.errors or parsed.unsupported:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="Unsupported FDS syntax for effective audit",
        )
    if any(r.kind == "GEOM" for r in parsed.records):
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="GEOM cut-cell effective occupancy is unsupported",
        )
    meshes = [r for r in parsed.records if r.kind == "MESH"]
    if not meshes:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="No MESH namelists found in FDS input",
        )
    obstructions = [r for r in parsed.primitives if r.kind == "OBST"]
    holes = [r for r in parsed.primitives if r.kind == "HOLE"]
    vents = [r for r in parsed.records if r.kind == "VENT"]
    if vents and (
        solver_version != "6.11.1" or len(meshes) != 1 or holes
        or [r.values.get("T_END") for r in parsed.records if r.kind == "TIME"] != [[0]]
        or any(
            not v.id or set(v.values) != {"ID", "XB", "SURF_ID"}
            or v.values["SURF_ID"] != ["OPEN"] or v.values["ID"] != [v.id]
            for v in vents
        )
        or any(not r.id for r in obstructions)
    ):
        return GateResult(status=GateStatus.INCONCLUSIVE, reason="Only static exterior OPEN VENT on one FDS 6.11.1 setup mesh is supported")
    if holes:
        if solver_version != "6.11.1":
            return GateResult(
                status=GateStatus.INCONCLUSIVE,
                reason="Static HOLE SMV adapter requires FDS 6.11.1",
            )
        return _effective_static_hole(parsed, meshes, obstructions, holes, smv_text)
    if any("DEVC_ID" in r.values or "CTRL_ID" in r.values for r in obstructions):
        return GateResult(status=GateStatus.INCONCLUSIVE, reason="Dynamic obstruction occupancy is unsupported")
    expected = {r.id: r.values["XB"] for r in obstructions}
    lines = smv_text.splitlines()
    evidence = {
        "adapter_version": EFFECTIVE_ADAPTER_VERSION,
        "smv_sha256": hashlib.sha256(smv_text.encode()).hexdigest(),
        "smv_lines": len(lines),
    }
    starts = [i for i, line in enumerate(lines) if line.split(maxsplit=1)[:1] == ["GRID"]]
    if not starts and len(meshes) == 1:
        starts = [0]  # Legacy single-mesh SMV fixture without a GRID heading.
    if len(starts) != len(meshes):
        return GateResult(status=GateStatus.INCONCLUSIVE, reason="SMV mesh sections do not match FDS input", evidence=evidence)
    if vents:
        try:
            grid_data = read_mesh_obstructions(meshes[0], lines)
        except (ValueError, IndexError) as exc:
            return GateResult(status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence)
        result = _effective_mesh(meshes[0], lines, expected, evidence, grid_data=grid_data)
        if result.status != GateStatus.PASS:
            return result
        mesh_id = meshes[0].id or "1"
        evidence["mesh_obstructions"] = {mesh_id: evidence["effective_bounds"]}
        return verify_open_vents(meshes[0], vents, lines, grid_data, evidence)
    domains = [mesh.values["XB"] for mesh in meshes]
    for i, left in enumerate(domains):
        for right in domains[i + 1:]:
            if _box_volume(_intersection(left, right)) > 0:
                return GateResult(status=GateStatus.INCONCLUSIVE, reason="Overlapping FDS meshes are unsupported", evidence=evidence)

    parts = {pid: [] for pid in expected}
    evidence["mesh_obstructions"] = {}
    for i, (start, stop, mesh, domain) in enumerate(zip(starts, starts[1:] + [len(lines)], meshes, domains)):
        clipped = {pid: _intersection(xb, domain) for pid, xb in expected.items()}
        clipped = {pid: xb for pid, xb in clipped.items() if _box_volume(xb) > 0}
        outcome = _effective_mesh(mesh, lines[start:stop], clipped, {})
        mesh_id = mesh.id or str(i + 1)
        evidence["mesh_obstructions"][mesh_id] = outcome.evidence.get("effective_bounds", {})
        if outcome.status != GateStatus.PASS:
            return GateResult(status=outcome.status, reason=f"Mesh {mesh_id}: {outcome.reason}", evidence=evidence)
        for pid, xb in outcome.evidence["effective_bounds"].items():
            parts[pid].append(xb)

    actual = {}
    for pid, boxes in parts.items():
        original_volume = _box_volume(expected[pid])
        covered_volume = math.fsum(_box_volume(_intersection(expected[pid], d)) for d in domains)
        if not boxes or not math.isclose(covered_volume, original_volume, rel_tol=1e-9, abs_tol=1e-12):
            return GateResult(status=GateStatus.INCONCLUSIVE, reason=f"Input solid is not covered by the solver meshes: {pid}", evidence=evidence)
        envelope = [op(box[i] for box in boxes) for i, op in enumerate((min, max) * 3)]
        if not math.isclose(_box_volume(envelope), math.fsum(map(_box_volume, boxes)), rel_tol=1e-9, abs_tol=1e-12):
            return GateResult(status=GateStatus.INCONCLUSIVE, reason=f"Effective pieces do not form a continuous box: {pid}", evidence=evidence)
        actual[pid] = envelope
    evidence["effective_bounds"] = actual
    return _check_clearances(expected, actual, evidence)


def _intersection(left, right):
    return [op(a, b) for op, a, b in zip((max, min) * 3, left, right)]


def _box_volume(box):
    return math.prod(max(0.0, box[i + 1] - box[i]) for i in (0, 2, 4))


def _grid_aligned_box(record, grids):
    indices = []
    for i, coordinate in enumerate(record.values["XB"]):
        matches = np.flatnonzero(np.abs(np.asarray(grids[i // 2]) - coordinate) <= 1e-7)
        if len(matches) != 1:
            raise ValueError(f"Static HOLE audit requires grid-aligned bounds: {record.id}")
        indices.append(int(matches[0]))
    if _box_volume(indices) <= 0:
        raise ValueError(f"Static HOLE audit requires a positive-volume box: {record.id}")
    return indices


def _on_exterior_mesh_face(indices, grids):
    flat = [i for i in (0, 2, 4) if indices[i] == indices[i + 1]]
    if len(flat) != 1:
        return False
    i = flat[0]
    return indices[i] in (0, len(grids[i // 2]) - 1)


def _effective_static_hole(parsed, meshes, obstructions, holes, smv_text):
    lines = smv_text.splitlines()
    evidence = {
        "adapter_version": EFFECTIVE_ADAPTER_VERSION,
        "smv_sha256": hashlib.sha256(smv_text.encode()).hexdigest(),
        "smv_lines": len(lines),
    }
    times = [r.values.get("T_END") for r in parsed.records if r.kind == "TIME"]
    if len(meshes) != 1 or len(obstructions) != 1 or len(holes) != 1 or times != [[0]]:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="Static HOLE proof requires a setup run with one mesh, wall and opening",
            evidence=evidence,
        )
    wall, hole = obstructions[0], holes[0]
    if (
        not wall.id
        or set(wall.values) - {"ID", "XB"}
        or set(hole.values) - {"ID", "XB"}
    ):
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="Static HOLE parameters are outside the reviewed obstruction subset",
            evidence=evidence,
        )
    try:
        grids, rows = read_mesh_obstructions(meshes[0], lines)
        host = _grid_aligned_box(wall, grids)
        cut = _grid_aligned_box(hole, grids)
        axes = [
            i for i in (0, 2, 4) if cut[i] < host[i] and host[i + 1] < cut[i + 1]
        ]
        if len(axes) != 1:
            raise ValueError("Static HOLE must cut through exactly one wall axis")
        normal = axes[0]
        tangents = [i for i in (0, 2, 4) if i != normal]
        for i in tangents:
            # A cut may reach a wall edge only at the exterior mesh boundary.
            # An internal coincident edge can retain a flow-blocking thin face.
            last = len(grids[i // 2]) - 1
            if (
                cut[i] < host[i] or cut[i + 1] > host[i + 1]
                or (cut[i] == host[i] and host[i] != 0)
                or (cut[i + 1] == host[i + 1] and host[i + 1] != last)
            ):
                raise ValueError("Static HOLE opening meets an unsupported wall edge")
        passage = _intersection(host, cut)
    except (ValueError, IndexError) as exc:
        return GateResult(status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence)

    pieces = [indices for _, indices in rows]
    if not pieces or any(label != wall.id for label, _ in rows):
        return GateResult(
            status=GateStatus.FAIL,
            reason="Static HOLE solver obstruction inventory differs from input wall",
            evidence=evidence,
        )
    boundary_faces = [piece for piece in pieces if _box_volume(piece) == 0]
    # The supported single mesh has no VENT or periodic boundary. A wall
    # fragment on an exterior face changes no interior gas-to-gas face.
    if any(not _on_exterior_mesh_face(piece, grids) for piece in boundary_faces):
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="Thin internal obstruction requires separate face occupancy evidence",
            evidence=evidence,
        )
    occupied = sum(_box_volume(piece) for piece in pieces)
    expected = _box_volume(host) - _box_volume(passage)
    evidence["static_hole"] = dict(
        wall_id=wall.id,
        opening_id=hole.id,
        through_axis="XYZ"[normal // 2],
        wall_indices=host,
        passage_indices=passage,
        obstruction_pieces=pieces,
        domain_boundary_faces=boundary_faces,
        effective_wall_cells=occupied,
        expected_wall_cells=expected,
    )
    if (
        occupied != expected
        or any(_intersection(piece, host) != piece for piece in pieces)
        or any(_box_volume(_intersection(piece, passage)) > 0 for piece in pieces)
        or any(
            _box_volume(_intersection(left, right)) > 0
            for i, left in enumerate(pieces)
            for right in pieces[i + 1:]
        )
    ):
        return GateResult(
            status=GateStatus.FAIL,
            reason="Solver cells differ from the wall minus the through-opening",
            evidence=evidence,
        )
    evidence["static_hole"]["open_area_m2"] = math.prod(
        grids[i // 2][passage[i + 1]] - grids[i // 2][passage[i]] for i in tangents
    )
    return GateResult(
        status=GateStatus.PASS,
        reason="Static wall and through-opening occupancy verified from solver SMV indices",
        evidence=evidence,
    )


def _effective_mesh(mesh, lines, expected, evidence, *, grid_data=None):
    try:
        grids, rows = grid_data if grid_data is not None else read_mesh_obstructions(mesh, lines)
        actual = {}
        for pid, indices in rows:
            if pid in actual:
                raise ValueError("Ambiguous SMV obstruction identity")
            actual[pid] = grid_bounds(indices, grids)
        evidence["effective_bounds"] = actual
    except (ValueError, IndexError) as exc:
        return GateResult(
            status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence
        )
    if set(actual) != set(expected):
        return GateResult(
            status=GateStatus.FAIL,
            reason="Solver obstruction inventory differs from input",
            evidence=evidence,
        )
    for pid, bounds in actual.items():
        for axis in range(3):
            low, high = bounds[2 * axis : 2 * axis + 2]
            if high <= low:
                return GateResult(
                    status=GateStatus.FAIL,
                    reason=f"Solid collapsed on FDS mesh: {pid}",
                    evidence=evidence,
                )
            half_cell = max(np.diff(grids[axis])) * 0.5 + 1e-8
            for side in (0, 1):
                distances = np.abs(
                    np.asarray(grids[axis]) - expected[pid][2 * axis + side]
                )
                nearest = np.flatnonzero(np.abs(distances - distances.min()) < 1e-8)
                if len(nearest) != 1:
                    return GateResult(
                        status=GateStatus.INCONCLUSIVE,
                        reason=f"Unproved half-cell rounding tie: {pid}",
                        evidence=evidence,
                    )
                if abs(bounds[2 * axis + side] - grids[axis][nearest[0]]) > 1e-7:
                    return GateResult(
                        status=GateStatus.FAIL,
                        reason=f"Unexpected effective cell occupancy: {pid}",
                        evidence=evidence,
                    )
            if any(
                abs(bounds[2 * axis + s] - expected[pid][2 * axis + s]) > half_cell
                for s in (0, 1)
            ):
                return GateResult(
                    status=GateStatus.FAIL,
                    reason=f"Unexpected grid displacement: {pid}",
                    evidence=evidence,
                )
    return _check_clearances(expected, actual, evidence)


def _check_clearances(expected, actual, evidence):
    ids = list(expected)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            a, b = expected[left], expected[right]
            aa, bb = actual[left], actual[right]
            for axis in range(3):
                others = [k for k in range(3) if k != axis]
                if not all(
                    min(a[2 * k + 1], b[2 * k + 1]) > max(a[2 * k], b[2 * k])
                    for k in others
                ):
                    continue
                gap = max(b[2 * axis] - a[2 * axis + 1], a[2 * axis] - b[2 * axis + 1])
                effective_gap = max(
                    bb[2 * axis] - aa[2 * axis + 1], aa[2 * axis] - bb[2 * axis + 1]
                )
                if gap > 1e-8 and effective_gap <= 1e-8:
                    return GateResult(
                        status=GateStatus.FAIL,
                        reason=f"Passage closed by FDS grid: {left}, {right}",
                        evidence=evidence,
                    )
    return GateResult(
        status=GateStatus.PASS,
        reason="OBST identities, grid displacement, solid thickness and pairwise clearances verified from solver SMV indices",
        evidence=evidence,
    )
