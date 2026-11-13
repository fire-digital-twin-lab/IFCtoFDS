"""Đọc chỉ số lưới trong các bảng hình học SMV của FDS 6.11.1."""

import numpy as np


def table_start(lines, tag):
    starts = [i + 1 for i, line in enumerate(lines) if line.strip() == tag]
    if len(starts) != 1:
        raise ValueError(f"Missing or multiple SMV {tag} tables")
    return starts[0]


def grid_bounds(indices, grids):
    if len(indices) != 6:
        raise ValueError("SMV requires six grid indices")
    if any(
        not 0 <= indices[i] <= indices[i + 1] < len(grids[i // 2])
        for i in (0, 2, 4)
    ):
        raise ValueError("Reversed SMV bounds or index outside coordinate grid")
    return [grids[i // 2][index] for i, index in enumerate(indices)]


def read_mesh_obstructions(mesh, lines):
    grids = []
    for axis, tag in enumerate(("TRNX", "TRNY", "TRNZ")):
        start = table_start(lines, tag)
        count = int(lines[start])
        if count < 0:
            raise ValueError("Invalid SMV grid transform count")
        start += 1 + count
        n = int(mesh.values["IJK"][axis]) + 1
        grid = []
        for index, line in enumerate(lines[start : start + n]):
            fields = line.split()
            if int(fields[0]) != index:
                raise ValueError("Unexpected SMV grid index")
            grid.append(float(fields[1]))
        if len(grid) != n or not np.isfinite(grid).all() or np.any(np.diff(grid) <= 0):
            raise ValueError("Invalid SMV coordinates")
        domain = mesh.values["XB"]
        if not np.allclose(
            grid, np.linspace(domain[2 * axis], domain[2 * axis + 1], n),
            atol=1e-7, rtol=0,
        ):
            raise ValueError("Nonuniform/unmatched solver grid is unsupported")
        grids.append(grid)

    start = table_start(lines, "OBST")
    count = int(lines[start])
    start += 1
    if count < 0 or start + 2 * count > len(lines):
        raise ValueError("Invalid SMV obstruction count")
    rows = []
    for i in range(count):
        _, marker, label = lines[start + i].partition("!")
        indices = [int(v) for v in lines[start + count + i].split()[:6]]
        if not marker or not label.strip():
            raise ValueError("Ambiguous SMV obstruction identity")
        grid_bounds(indices, grids)
        rows.append((label.strip(), indices))
    return grids, rows
