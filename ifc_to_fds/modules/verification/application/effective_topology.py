"""Air connectivity on an exact common rectilinear partition of OBST bounds.

This is a geometric six-neighbour connectivity proof, not an airflow model.
Source and solver planes both split the partition, so sub-cell passages are
represented without sampling them at solver cell centres.
"""

import math

import numpy as np
from scipy.ndimage import label

from ifc_to_fds.domain.validation import GateResult, GateStatus

CELL_BUDGET = 2_000_000


def verify_air_paths(expected, actual, domain):
    evidence = {"scope": "RECTILINEAR_OBST_AIR_CONNECTIVITY", "cell_budget": CELL_BUDGET}

    def result(status, reason):
        return GateResult(status=status, reason=reason, evidence=evidence)

    if any(
        box[i] < domain[i] if i % 2 == 0 else box[i] > domain[i]
        for boxes in (expected, actual)
        for box in boxes.values()
        for i in range(6)
    ):
        return result(
            GateStatus.INCONCLUSIVE, "Out-of-domain OBST requires a boundary audit"
        )
    planes = []
    for axis in range(3):
        coordinates = list(domain[2 * axis : 2 * axis + 2])
        for boxes in (expected, actual):
            for box in boxes.values():
                coordinates.extend(box[2 * axis : 2 * axis + 2])
        planes.append(np.unique(coordinates))
    shape = tuple(len(p) - 1 for p in planes)
    evidence["partition_shape"] = shape
    if math.prod(shape) > CELL_BUDGET:
        return result(
            GateStatus.INCONCLUSIVE,
            "Air connectivity partition exceeds adapter resource budget",
        )

    def cells(box):
        ranges = [
            np.searchsorted(planes[k], box[2 * k : 2 * k + 2]) for k in range(3)
        ]
        return tuple(slice(int(low), int(high)) for low, high in ranges)

    def components(boxes):
        air = np.ones(shape, dtype=bool)
        for box in boxes.values():
            air[cells(box)] = False
        return label(air)  # Default structure: six face-adjacent neighbours.

    source, source_count = components(expected)
    effective, effective_count = components(actual)
    evidence.update(source_components=source_count, effective_components=effective_count)
    evidence["boundary_clearance_scope"] = "AIR_COLUMNS_OUTSIDE_THE_UNION_OF_ALL_OBST"
    evidence["boundary_clearances"] = {}
    for pid, box in expected.items():
        clearances = evidence["boundary_clearances"][pid] = []
        for axis in range(3):
            for side in (0, 1):
                i = 2 * axis + side
                gap = (box[i] - domain[i]) * (1 if side == 0 else -1)
                effective_gap = (actual[pid][i] - domain[i]) * (1 if side == 0 else -1)
                clearance = {
                    "axis": axis, "side": side,
                    "source_m": gap, "effective_m": effective_gap,
                }
                clearances.append(clearance)
                if gap > 1e-8 and effective_gap <= 1e-8:
                    corridor = list(box)
                    corridor[2 * axis : 2 * axis + 2] = (
                        [domain[i], box[i]] if side == 0 else [box[i], domain[i]]
                    )
                    region = cells(corridor)
                    # A distance to one OBST is not an air passage when other
                    # OBSTs already cover it. Compare clear columns through the
                    # whole source gap using the independently built unions.
                    source_clear = np.all(source[region] > 0, axis=axis)
                    effective_clear = np.all(effective[region] > 0, axis=axis)
                    closed = int(np.count_nonzero(source_clear & ~effective_clear))
                    clearance.update(
                        source_clear_columns=int(source_clear.sum()),
                        effective_clear_columns=int(effective_clear.sum()),
                        closed_columns=closed,
                    )
                    if closed:
                        return result(
                            GateStatus.FAIL,
                            f"Passage closed at domain boundary: {pid}, axis {axis}, side {side}",
                        )
    # A bijection via shared air cells detects split, merged, vanished and newly
    # created components, including split/merge pairs with unchanged total count.
    common = (source > 0) & (effective > 0)
    pairs = np.unique(np.column_stack((source[common], effective[common])), axis=0)
    bijective = (
        len(pairs) == source_count == effective_count
        and len(np.unique(pairs[:, 0])) == source_count
        and len(np.unique(pairs[:, 1])) == effective_count
    )
    evidence["component_correspondence"] = pairs.tolist()
    if not bijective:
        return result(GateStatus.FAIL, "Air connectivity changed by FDS grid")
    return result(
        GateStatus.PASS,
        "Domain boundary clearances and air component correspondence preserved",
    )
