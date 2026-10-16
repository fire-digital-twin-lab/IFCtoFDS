"""FDS 6.11.1 SMV obstruction indices for the single-mesh OBST subset.

Format reference: firemodels/fds FDS-6.11.1 Source/dump.f90, SMV OBST
section. Physical bounds come from TRNX/Y/Z at the solver's integer indices,
not the original unsnapped coordinates in the first OBST table.
"""

import hashlib
import numpy as np
from .acceptance import GateResult, GateStatus
from .parser import parse_fds


def effective_obstructions(fds_text, smv_text):
    parsed = parse_fds(fds_text)
    if parsed.errors or parsed.unsupported:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="Unsupported FDS syntax for effective audit",
        )
    if any(r.kind in ("GEOM", "HOLE", "VENT") for r in parsed.records):
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="GEOM cut-cell and HOLE/VENT effective output adapters are not implemented",
        )
    meshes = [r for r in parsed.records if r.kind == "MESH"]
    if len(meshes) != 1:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="Effective OBST audit requires one mesh",
        )
    lines = smv_text.splitlines()
    expected = {r.id: r.values["XB"] for r in parsed.primitives if r.kind == "OBST"}
    evidence = {
        "smv_sha256": hashlib.sha256(smv_text.encode()).hexdigest(),
        "smv_text": smv_text,
    }
    try:
        grids = []
        for axis, tag in enumerate(("TRNX", "TRNY", "TRNZ")):
            starts = [i for i, line in enumerate(lines) if line.strip() == tag]
            if len(starts) != 1:
                raise ValueError("Missing or multiple SMV coordinate grids")
            start = starts[0] + 1
            count = int(lines[start])
            start += 1 + count
            n = int(meshes[0].values["IJK"][axis]) + 1
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
            half_cell = max(np.diff(grids[axis])) * 0.5 + 1e-8
            if any(
                abs(bounds[2 * axis + s] - expected[pid][2 * axis + s]) > half_cell
                for s in (0, 1)
            ):
                return GateResult(
                    status=GateStatus.FAIL,
                    reason=f"Unexpected grid displacement: {pid}",
                    evidence=evidence,
                )
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
        reason="Single-mesh OBST identities, grid displacement, solid thickness and pairwise clearances verified from solver SMV indices",
        evidence=evidence,
    )
