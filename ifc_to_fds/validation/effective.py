"""FDS 6.11.1 SMV obstruction indices for static OBST on disjoint meshes.

Format reference: firemodels/fds FDS-6.11.1 Source/dump.f90, SMV OBST
section. Physical bounds come from TRNX/Y/Z at the solver's integer indices,
not the original unsnapped coordinates in the first OBST table.
"""

import hashlib
import math
import numpy as np
from ifc_to_fds.geometry.mesh import bounds_for_vertices, is_axis_aligned_box
from .acceptance import GateResult, GateStatus
from .parser import parse_fds


# The SMV prints coordinates with five decimals, so a grid that is not a round multiple of the cell size
# differs from the FDS input by up to 5e-6 m. Anything closer than this cannot be told apart from the print.
SMV_PRECISION_M = 1e-5


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


def effective_obstructions(fds_text, smv_text):
    parsed = parse_fds(fds_text)
    if parsed.errors or parsed.unsupported:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="Unsupported FDS syntax for effective audit",
        )
    if any(r.kind == "HOLE" for r in parsed.records):
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="HOLE effective output adapter is not implemented",
        )
    meshes = [r for r in parsed.records if r.kind == "MESH"]
    if not meshes:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="No MESH namelists found in FDS input",
        )
    obstructions = [r for r in parsed.primitives if r.kind == "OBST"]
    # What the SMV cannot confirm is reported per element and never hides a verified failure elsewhere.
    elements = {
        r.id or "GEOM": dict(kind="GEOM", status="INCONCLUSIVE", reason="GEOM cut-cell output is not read from the SMV")
        for r in parsed.records
        if r.kind == "GEOM"
    }
    dynamic = {r.id for r in obstructions if "DEVC_ID" in r.values or "CTRL_ID" in r.values}
    vents = [r for r in parsed.records if r.kind == "VENT"]
    expected = {r.id: r.values["XB"] for r in obstructions}
    lines = smv_text.splitlines()
    evidence = {"smv_sha256": hashlib.sha256(smv_text.encode()).hexdigest(), "smv_lines": len(lines)}
    starts = [i for i, line in enumerate(lines) if line.split(maxsplit=1)[:1] == ["GRID"]]
    if not starts and len(meshes) == 1:
        starts = [0]  # Legacy single-mesh SMV fixture without a GRID heading.
    if len(starts) != len(meshes):
        return GateResult(status=GateStatus.INCONCLUSIVE, reason="SMV mesh sections do not match FDS input", evidence=evidence)
    domains = [mesh.values["XB"] for mesh in meshes]
    for i, left in enumerate(domains):
        for right in domains[i + 1:]:
            if _box_volume(_intersection(left, right)) > 0:
                return GateResult(status=GateStatus.INCONCLUSIVE, reason="Overlapping FDS meshes are unsupported", evidence=evidence)

    parts = {pid: [] for pid in expected}
    evidence["mesh_obstructions"] = {}
    labels, vent_pieces = _vent_labels(lines), {}
    for i, (start, stop, mesh, domain) in enumerate(zip(starts, starts[1:] + [len(lines)], meshes, domains)):
        clipped = {pid: _intersection(xb, domain) for pid, xb in expected.items()}
        clipped = {pid: xb for pid, xb in clipped.items() if _box_volume(xb) > 0}
        outcome = _effective_mesh(mesh, lines[start:stop], clipped, {}, dynamic)
        mesh_id = mesh.id or str(i + 1)
        evidence["mesh_obstructions"][mesh_id] = outcome.evidence.get("effective_bounds", {})
        if outcome.status != GateStatus.PASS:
            return GateResult(status=outcome.status, reason=f"Mesh {mesh_id}: {outcome.reason}", evidence=evidence)
        for vid, result in _effective_vents(mesh, lines[start:stop], vents, domain, labels).items():
            vent_pieces.setdefault(vid, []).append(result)
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
    for vent in vents:
        if not vent.id:
            elements["VENT"] = dict(kind="VENT", status="INCONCLUSIVE", reason="Vent has no ID to match in the SMV")
        elif vent.id not in vent_pieces:
            elements[vent.id] = dict(kind="VENT", status="INCONCLUSIVE", reason="Vent is not inside any solver mesh")
    for vid, pieces in vent_pieces.items():
        worst = next((p for p in pieces if p[0] == "FAIL"), next((p for p in pieces if p[0] != "PASS"), None))
        elements[vid] = dict(kind="VENT", status=worst[0] if worst else "PASS", reason=worst[1] if worst else "Snapped vent bounds verified")
    evidence["elements"] = elements
    evidence["dynamic_obstructions"] = sorted(dynamic)
    clearance = _check_clearances(expected, actual, evidence, dynamic)
    if clearance.status != GateStatus.PASS:
        return clearance
    failed = [f"{i}: {e['reason']}" for i, e in elements.items() if e["status"] == "FAIL"]
    unknown = [f"{i}: {e['reason']}" for i, e in elements.items() if e["status"] == "INCONCLUSIVE"]
    verified = sum(e["status"] == "PASS" for e in elements.values()) + len(actual)
    if failed:
        return GateResult(status=GateStatus.FAIL, reason="; ".join(failed[:5]), evidence=evidence)
    if unknown:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason=f"{len(unknown)} element(s) not verifiable ({'; '.join(unknown[:3])}); {verified} OBST/VENT verified",
            evidence=evidence,
        )
    return clearance


def _vent_labels(lines):
    """Input vent IDs in input order: the solver numbers its vents by that order."""
    for i, line in enumerate(lines):
        if line.strip() == "VENTORIG" and i + 1 < len(lines):
            count = int(lines[i + 1])
            return [row.partition("!")[2].strip() for row in lines[i + 2 : i + 2 + count]]
    return []


def _effective_vents(mesh, lines, vents, domain, labels):
    """{vent id: (status, reason)} for each flat input vent that has area in this mesh."""
    try:
        grids = _grids(mesh, lines)
    except (ValueError, IndexError):
        grids = None
    out = {}
    table = next((i for i, line in enumerate(lines) if line.strip() == "VENT"), None)
    rows = {}
    if grids and table is not None:
        count = int(lines[table + 1].split()[0])
        for n in range(count):
            head = lines[table + 2 + n].split()
            indices = [int(v) for v in lines[table + 2 + count + n].split()[:6]]
            if len(head) >= 8 and int(head[7]) > 0 and int(head[7]) <= len(labels):
                rows[labels[int(head[7]) - 1]] = indices
    for vent in vents:
        xb = vent.values.get("XB", [])
        flat = [a for a in range(3) if len(xb) == 6 and xb[2 * a] == xb[2 * a + 1]]
        if not vent.id or len(flat) != 1:
            continue
        piece = _intersection(xb, domain)
        if any(piece[2 * a + 1] < piece[2 * a] for a in range(3)):
            continue
        tangents = [a for a in range(3) if a != flat[0]]
        if any(piece[2 * a + 1] <= piece[2 * a] for a in tangents):
            continue  # touches this mesh only along an edge
        if grids is None or table is None:
            out[vent.id] = ("INCONCLUSIVE", "SMV has no readable VENT table for this mesh")
        elif vent.id not in rows:
            out[vent.id] = ("FAIL", "Vent missing from the solver output (collapsed by the grid or dropped)")
        else:
            out[vent.id] = _vent_outcome(piece, flat[0], rows[vent.id], grids)
    return out


def _vent_outcome(piece, normal, indices, grids):
    snapped = [grids[a][indices[2 * a + side]] for a in range(3) for side in (0, 1)]
    for a in range(3):
        for side in (0, 1):
            distances = np.abs(np.asarray(grids[a]) - piece[2 * a + side])
            nearest = np.flatnonzero(np.abs(distances - distances.min()) < SMV_PRECISION_M)
            if len(nearest) != 1:
                return "INCONCLUSIVE", "Unproved half-cell rounding tie"
            if abs(snapped[2 * a + side] - grids[a][nearest[0]]) > 1e-7:
                return "FAIL", "Unexpected effective cell occupancy"
        if a != normal and snapped[2 * a + 1] <= snapped[2 * a]:
            return "FAIL", "Vent collapsed on FDS mesh"
    return "PASS", "Snapped vent bounds verified"


def _intersection(left, right):
    return [op(a, b) for op, a, b in zip((max, min) * 3, left, right)]


def _box_volume(box):
    return math.prod(max(0.0, box[i + 1] - box[i]) for i in (0, 2, 4))


def _grids(mesh, lines):
    """Solver coordinate planes per axis, read from the SMV TRNX/Y/Z tables."""
    grids = []
    for axis, tag in enumerate(("TRNX", "TRNY", "TRNZ")):
        starts = [i for i, line in enumerate(lines) if line.strip() == tag]
        if len(starts) != 1:
            raise ValueError("Missing or multiple SMV coordinate grids")
        start = starts[0] + 1
        count = int(lines[start])
        start += 1 + count
        n = int(mesh.values["IJK"][axis]) + 1
        grid = []
        for index, line in enumerate(lines[start : start + n]):
            fields = line.split()
            if int(fields[0]) != index:
                raise ValueError("Unexpected SMV grid index")
            grid.append(float(fields[1]))
        if (
            len(grid) != n
            or not np.isfinite(grid).all()
            or np.any(np.diff(grid) <= 0)
        ):
            raise ValueError("Invalid SMV coordinates")
        grids.append(grid)
    for axis, grid in enumerate(grids):
        domain = mesh.values["XB"]
        if not np.allclose(
            grid, np.linspace(domain[2 * axis], domain[2 * axis + 1], len(grid)),
            atol=SMV_PRECISION_M, rtol=0,
        ):
            raise ValueError("Nonuniform/unmatched solver grid is unsupported")
    return grids


def _effective_mesh(mesh, lines, expected, evidence, dynamic=frozenset()):
    try:
        grids = _grids(mesh, lines)

        starts = [i for i, line in enumerate(lines) if line.strip() == "OBST"]
        if len(starts) != 1:
            raise ValueError("Missing or multiple SMV OBST tables")
        start = starts[0] + 1
        count = int(lines[start])
        start += 1
        actual = {}
        for i in range(count):
            _, marker, label = lines[start + i].partition("!")
            indices = [int(v) for v in lines[start + count + i].split()[:6]]
            if not marker or len(indices) != 6 or label.strip() in actual:
                raise ValueError("Ambiguous SMV obstruction identity")
            if any(
                indices[2 * axis + side] < 0
                or indices[2 * axis + side] >= len(grids[axis])
                for axis in range(3)
                for side in range(2)
            ):
                raise ValueError("SMV obstruction index outside coordinate grid")
            actual[label.strip()] = [
                grids[axis][indices[2 * axis + side]]
                for axis in range(3)
                for side in range(2)
            ]
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
            half_cell = max(np.diff(grids[axis])) * 0.5 + SMV_PRECISION_M
            for side in (0, 1):
                distances = np.abs(
                    np.asarray(grids[axis]) - expected[pid][2 * axis + side]
                )
                nearest = np.flatnonzero(np.abs(distances - distances.min()) < SMV_PRECISION_M)
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
    return _check_clearances(expected, actual, evidence, dynamic)


def _check_clearances(expected, actual, evidence, dynamic=frozenset()):
    # Pairs with a controlled obstruction are skipped: closed, it may legitimately seal its frame, and
    # open, only the static pairs remain, which are checked here.
    ids = [i for i in expected if i not in dynamic]
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
