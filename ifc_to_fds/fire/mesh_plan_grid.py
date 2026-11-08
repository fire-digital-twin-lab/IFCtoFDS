"""Low-level coarse-grid lattice and partition utilities for Local MeshPlan."""

from __future__ import annotations

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.validation.parser import parse_fds

from .mesh_plan_models import MeshRegion

NUMERIC_TOLERANCE_M = 2e-6
MAX_CELLS_PER_MESH = 500_000


def box_volume(bounds: BoundingBox) -> float:
    return bounds.dx * bounds.dy * bounds.dz


def within(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        inner.xmin >= outer.xmin - NUMERIC_TOLERANCE_M
        and inner.xmax <= outer.xmax + NUMERIC_TOLERANCE_M
        and inner.ymin >= outer.ymin - NUMERIC_TOLERANCE_M
        and inner.ymax <= outer.ymax + NUMERIC_TOLERANCE_M
        and inner.zmin >= outer.zmin - NUMERIC_TOLERANCE_M
        and inner.zmax <= outer.zmax + NUMERIC_TOLERANCE_M
    )


def contains_strict(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        inner.xmin > outer.xmin + NUMERIC_TOLERANCE_M
        and inner.xmax < outer.xmax - NUMERIC_TOLERANCE_M
        and inner.ymin > outer.ymin + NUMERIC_TOLERANCE_M
        and inner.ymax < outer.ymax - NUMERIC_TOLERANCE_M
        and inner.zmin > outer.zmin + NUMERIC_TOLERANCE_M
        and inner.zmax < outer.zmax - NUMERIC_TOLERANCE_M
    )


def lattice_index(
    value: float,
    origin: float,
    spacing: float,
    cells: int,
    label: str,
) -> int:
    raw = (float(value) - origin) / spacing
    index = int(round(raw))
    if (
        index < 0
        or index > cells
        or abs(float(value) - (origin + index * spacing)) > NUMERIC_TOLERANCE_M
    ):
        raise ValueError(f"{label} must align with the verified coarse-grid lattice")
    return index


def normalize_axis_interval(
    lower: int,
    upper: int,
    total: int,
    axis_name: str,
) -> tuple[int, int, list[str]]:
    """Expand interval to avoid one-cell 3D meshes and one-cell local spans."""

    if total < 2:
        raise ValueError(
            f"LocalMeshPlan requires at least 2 coarse cells along {axis_name}"
        )
    if upper <= lower:
        raise ValueError(f"LocalMeshPlan has empty {axis_name} interval")

    original_lower, original_upper = lower, upper
    if upper - lower == 1:
        if upper < total:
            upper += 1
        elif lower > 0:
            lower -= 1
        else:
            raise ValueError(
                f"Cannot create a 3D local mesh with one coarse cell along {axis_name}"
            )

    if lower == 1:
        lower = 0
    if total - upper == 1:
        upper = total

    adjustments: list[str] = []
    if lower != original_lower:
        adjustments.append(
            f"{axis_name}min coarse index expanded {original_lower}->{lower}"
        )
    if upper != original_upper:
        adjustments.append(
            f"{axis_name}max coarse index expanded {original_upper}->{upper}"
        )
    return lower, upper, adjustments


def bounds_from_indices(
    domain: BoundingBox,
    spacing: tuple[float, float, float],
    block: tuple[int, int, int, int, int, int],
) -> BoundingBox:
    ix0, ix1, iy0, iy1, iz0, iz1 = block
    return BoundingBox(
        xmin=domain.xmin + ix0 * spacing[0],
        xmax=domain.xmin + ix1 * spacing[0],
        ymin=domain.ymin + iy0 * spacing[1],
        ymax=domain.ymin + iy1 * spacing[1],
        zmin=domain.zmin + iz0 * spacing[2],
        zmax=domain.zmin + iz1 * spacing[2],
    )


def split_coarse_block(
    block: tuple[int, int, int, int, int, int],
) -> list[tuple[int, int, int, int, int, int]]:
    """Split a lattice block without changing verified coarse spacing."""

    ix0, ix1, iy0, iy1, iz0, iz1 = block
    counts = (ix1 - ix0, iy1 - iy0, iz1 - iz0)
    if min(counts) <= 0:
        return []
    if counts[0] * counts[1] * counts[2] <= MAX_CELLS_PER_MESH:
        return [block]

    axis = max(range(3), key=lambda index: counts[index])
    if counts[axis] <= 1:
        raise ValueError("Coarse mesh cannot be partitioned below the cell limit")
    if axis == 0:
        middle = ix0 + counts[0] // 2
        pair = (
            (ix0, middle, iy0, iy1, iz0, iz1),
            (middle, ix1, iy0, iy1, iz0, iz1),
        )
    elif axis == 1:
        middle = iy0 + counts[1] // 2
        pair = (
            (ix0, ix1, iy0, middle, iz0, iz1),
            (ix0, ix1, middle, iy1, iz0, iz1),
        )
    else:
        middle = iz0 + counts[2] // 2
        pair = (
            (ix0, ix1, iy0, iy1, iz0, middle),
            (ix0, ix1, iy0, iy1, middle, iz1),
        )
    return [piece for item in pair for piece in split_coarse_block(item)]


def validate_base_mesh_lattice(
    base_text: str,
    domain: BoundingBox,
    spacing: tuple[float, float, float],
    coarse_ijk: tuple[int, int, int],
) -> None:
    parsed = parse_fds(base_text)
    if parsed.errors or parsed.unsupported:
        raise ValueError("Verified base FDS cannot be parsed for MeshPlan replacement")
    records = [record for record in parsed.records if record.kind == "MESH"]
    if not records:
        raise ValueError("Verified base has no MESH records")

    for record in records:
        xb = [float(value) for value in record.values.get("XB", [])]
        ijk = [int(value) for value in record.values.get("IJK", [])]
        if len(xb) != 6 or len(ijk) != 3:
            raise ValueError("Verified base MESH is incomplete")
        for axis, (origin, step, count) in enumerate(
            zip((domain.xmin, domain.ymin, domain.zmin), spacing, coarse_ijk)
        ):
            lattice_index(xb[2 * axis], origin, step, count, "Base MESH boundary")
            lattice_index(
                xb[2 * axis + 1],
                origin,
                step,
                count,
                "Base MESH boundary",
            )
            actual = (xb[2 * axis + 1] - xb[2 * axis]) / ijk[axis]
            if abs(actual - step) > max(NUMERIC_TOLERANCE_M, step * 1e-5):
                raise ValueError(
                    "Verified base MESH does not use one uniform coarse-grid lattice"
                )


def validate_partition(domain: BoundingBox, meshes: list[MeshRegion]) -> None:
    for index, left in enumerate(meshes):
        if not within(domain, left.bounds):
            raise ValueError(f"Mesh lies outside simulation domain: {left.id}")
        for right in meshes[index + 1 :]:
            if all(
                min(left.bounds.to_xb()[axis + 1], right.bounds.to_xb()[axis + 1])
                - max(left.bounds.to_xb()[axis], right.bounds.to_xb()[axis])
                > NUMERIC_TOLERANCE_M
                for axis in (0, 2, 4)
            ):
                raise ValueError(f"Mesh interiors overlap: {left.id}, {right.id}")

    covered = sum(box_volume(mesh.bounds) for mesh in meshes)
    domain_volume = box_volume(domain)
    if abs(covered - domain_volume) > max(1e-8, domain_volume * 1e-8):
        raise ValueError("MeshPlan does not cover the simulation domain exactly")
