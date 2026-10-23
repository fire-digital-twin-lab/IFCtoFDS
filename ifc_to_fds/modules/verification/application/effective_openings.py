"""Pinned SMV proof for static, grid-aligned OBST/HOLE and exterior OPEN vents.

Source: FDS-6.11.1 Source/dump.f90, SMV OBST, VENTORIG and VENT tables.
Compare per-source cell occupancy, not the unsnapped coordinate display table.
No cut-cell, dynamic opening, internal vent or unaligned-rounding claim is made.
"""

import hashlib
import math

import numpy as np
from scipy.ndimage import label

from ifc_to_fds.domain.validation import GateResult, GateStatus

CELL_BUDGET = 2_000_000
SMV_GRID_TOLERANCE = 1e-7


def effective_openings(parsed, smv_text):
    evidence = {
        "scope": "STATIC_GRID_ALIGNED_OBST_HOLE_AND_EXTERIOR_OPEN_VENT",
        "smv_sha256": hashlib.sha256(smv_text.encode()).hexdigest(),
        "cell_budget": CELL_BUDGET,
    }

    def result(status, reason):
        return GateResult(status=status, reason=reason, evidence=evidence)

    meshes = [r for r in parsed.records if r.kind == "MESH"]
    if len(meshes) != 1 or any(r.kind == "GEOM" for r in parsed.records):
        return result(
            GateStatus.INCONCLUSIVE,
            "Opening adapter requires one uniform Cartesian mesh without GEOM",
        )
    mesh = meshes[0]
    shape = tuple(int(n) for n in mesh.values["IJK"])
    if math.prod(shape) > CELL_BUDGET:
        return result(
            GateStatus.INCONCLUSIVE,
            "Cell occupancy audit exceeds configured adapter resource budget",
        )
    domain = mesh.values["XB"]
    lines = smv_text.splitlines()

    def section(name):
        starts = [i for i, line in enumerate(lines) if line.strip() == name]
        if len(starts) != 1:
            raise ValueError(f"Missing or ambiguous SMV {name}")
        return starts[0] + 1

    try:
        grids = []
        for axis, tag in enumerate(("TRNX", "TRNY", "TRNZ")):
            start = section(tag)
            start += 1 + int(lines[start])
            rows = [line.split() for line in lines[start : start + shape[axis] + 1]]
            if len(rows) != shape[axis] + 1 or any(
                int(row[0]) != i for i, row in enumerate(rows)
            ):
                raise ValueError("Invalid SMV grid indices")
            grid = np.array([float(row[1]) for row in rows])
            if (
                not np.isfinite(grid).all()
                or np.any(np.diff(grid) <= 0)
                or not np.allclose(
                    grid,
                    np.linspace(
                        domain[2 * axis], domain[2 * axis + 1], shape[axis] + 1
                    ),
                    rtol=0,
                    atol=SMV_GRID_TOLERANCE,
                )
            ):
                raise ValueError(
                    "Uniform solver grid not confirmed within SMV print precision"
                )
            grids.append(grid)

        def indices(xb):
            if len(xb) != 6:
                raise ValueError("Six coordinates required")
            found = []
            for i, x in enumerate(xb):
                distances = abs(grids[i // 2] - x)
                nearest = np.flatnonzero(distances <= SMV_GRID_TOLERANCE)
                if len(nearest) != 1:
                    raise ValueError(
                        "Opening adapter requires unambiguous grid-aligned input bounds"
                    )
                found.append(int(nearest[0]))
            if any(found[i] > found[i + 1] for i in (0, 2, 4)):
                raise ValueError("Reversed cell bounds")
            return found

        def slices(ix):
            return tuple(slice(ix[i], ix[i + 1]) for i in (0, 2, 4))

        def checked_indices(row):
            ix = [int(v) for v in row.split()[:6]]
            if (
                len(ix) != 6
                or any(ix[i] < 0 or ix[i] > shape[i // 2] for i in range(6))
                or any(ix[i] > ix[i + 1] for i in (0, 2, 4))
            ):
                raise ValueError("Invalid SMV cell bounds")
            return ix

        obstacles = [r for r in parsed.primitives if r.kind == "OBST"]
        holes = [r for r in parsed.primitives if r.kind == "HOLE"]
        vents = [r for r in parsed.primitives if r.kind == "VENT"]
        if math.prod(shape) * (2 * len(obstacles) + 3) > CELL_BUDGET:
            return result(
                GateStatus.INCONCLUSIVE,
                "Per-source occupancy arrays exceed adapter resource budget",
            )
        if not obstacles or any(not r.id for r in obstacles + holes + vents):
            raise ValueError("Source obstacle and opening identities required")
        hole_indices = {r.id: indices(r.values.get("XB", [])) for r in holes}
        expected = {}
        for r in obstacles:
            ix = indices(r.values["XB"])
            if any(ix[i] == ix[i + 1] for i in (0, 2, 4)):
                return result(GateStatus.FAIL, f"Source obstacle collapsed: {r.id}")
            mask = np.zeros(shape, dtype=bool)
            mask[slices(ix)] = True
            for cut in hole_indices.values():
                mask[slices(cut)] = False
            expected[r.id] = mask

        start = section("OBST")
        count = int(lines[start])
        if count < 0 or count > len(lines) // 2:
            raise ValueError("Invalid SMV obstruction count")
        start += 1
        actual = {pid: np.zeros(shape, dtype=bool) for pid in expected}
        for row in range(count):
            _, marker, pid = lines[start + row].partition("!")
            pid = pid.strip()
            if not marker or pid not in actual:
                return result(GateStatus.FAIL, "Unexpected solver obstruction identity")
            ix = checked_indices(lines[start + count + row])
            # FDS can emit a zero-thickness remnant at an existing domain face.
            # Internal baffles need a separate face-occupancy proof.
            for i in (0, 2, 4):
                if ix[i] == ix[i + 1] and ix[i] not in (0, shape[i // 2]):
                    raise ValueError(
                        "Internal zero-thickness obstruction requires face evidence"
                    )
            actual[pid][slices(ix)] = True
        evidence["obstacles"] = {}
        for pid in expected:
            changed = int(np.count_nonzero(expected[pid] != actual[pid]))
            evidence["obstacles"][pid] = {
                "expected_cells": int(expected[pid].sum()),
                "effective_cells": int(actual[pid].sum()),
                "mismatched_cells": changed,
            }
            if changed:
                return result(
                    GateStatus.FAIL,
                    f"Effective solid/opening cell occupancy differs: {pid}",
                )
        occupied = np.zeros(shape, dtype=bool)
        for mask in actual.values():
            occupied |= mask
        evidence["air_components_6_connected"] = int(label(~occupied)[1])
        evidence["openings"] = {
            pid: {
                "clear_cells": int(np.count_nonzero(~occupied[slices(ix)])),
                "blocked_cells": int(np.count_nonzero(occupied[slices(ix)])),
            }
            for pid, ix in hole_indices.items()
        }

        start = section("VENTORIG")
        count = int(lines[start])
        if count != len(vents):
            return result(GateStatus.FAIL, "Solver original vent inventory differs")
        ordinal_ids = []
        for row in range(count):
            coordinates, marker, pid = lines[start + 1 + row].partition("!")
            pid = pid.strip()
            if not marker or pid not in {r.id for r in vents} or pid in ordinal_ids:
                return result(GateStatus.FAIL, "Solver original vent identity differs")
            r = next(r for r in vents if r.id == pid)
            if indices([float(x) for x in coordinates.split()]) != indices(
                r.values.get("XB", [])
            ):
                return result(
                    GateStatus.FAIL, f"Solver original vent location differs: {pid}"
                )
            ordinal_ids.append(pid)
        start = section("VENT")
        total, dummy = map(int, lines[start].split())
        explicit = total - dummy
        if explicit != len(vents) or dummy < 0 or total < 0 or total > len(lines) // 2:
            return result(GateStatus.FAIL, "Effective explicit vent inventory differs")
        surfaces = [
            lines[i + 1].strip()
            for i, line in enumerate(lines)
            if line.strip() == "SURFACE"
        ]
        evidence["vents"] = {}
        seen = set()
        for row in range(explicit):
            fields = lines[start + 1 + row].split()
            ordinal, surface = int(fields[6]), int(fields[7])
            if ordinal < 1 or ordinal > len(ordinal_ids) or ordinal in seen:
                raise ValueError("Ambiguous effective vent ordinal")
            seen.add(ordinal)
            pid = ordinal_ids[ordinal - 1]
            r = next(r for r in vents if r.id == pid)
            if r.values.get("SURF_ID") != ["OPEN"]:
                raise ValueError("Only exterior OPEN vent semantics are supported")
            if surface < 0 or surface >= len(surfaces) or surfaces[surface] != "OPEN":
                return result(GateStatus.FAIL, f"Solver vent is not OPEN: {pid}")
            expected_ix = indices(r.values.get("XB", []))
            effective_ix = checked_indices(lines[start + 1 + total + row])
            if (
                indices([float(x) for x in fields[:6]]) != expected_ix
                or effective_ix != expected_ix
            ):
                return result(
                    GateStatus.FAIL, f"Effective vent cell footprint differs: {pid}"
                )
            planes = [i for i in (0, 2, 4) if expected_ix[i] == expected_ix[i + 1]]
            if len(planes) != 1 or expected_ix[planes[0]] not in (
                0,
                shape[planes[0] // 2],
            ):
                raise ValueError("Only planar exterior vents are supported")
            axis = planes[0] // 2
            adjacent = list(slices(expected_ix))
            cell = 0 if expected_ix[2 * axis] == 0 else shape[axis] - 1
            adjacent[axis] = slice(cell, cell + 1)
            if occupied[tuple(adjacent)].any():
                raise ValueError(
                    "Vent intersects solid cells; boundary patch proof required"
                )
            evidence["vents"][pid] = {
                "surface": "OPEN",
                "cell_indices": effective_ix,
                "adjacent_cells_clear": True,
            }
    except (ValueError, IndexError, TypeError, OverflowError) as exc:
        return result(GateStatus.INCONCLUSIVE, str(exc))
    return result(
        GateStatus.PASS,
        "Per-source solid/opening cell occupancy and exterior OPEN vent footprints verified from pinned solver SMV",
    )
