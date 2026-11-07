"""Deterministic non-overlapping layout resolver for Local MeshPlan."""

from __future__ import annotations

import math
from typing import Any

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.mapping.exporter import compute_mesh_grid
from ifc_to_fds.validation.parser import parse_fds

from .mesh_plan_models import LocalMeshPlanRequest, MeshRegion, ResolvedLocalMeshPlan

_NUMERIC_TOLERANCE_M = 2e-6
_MAX_CELLS_PER_MESH = 500_000


def _box_volume(bounds: BoundingBox) -> float:
    return bounds.dx * bounds.dy * bounds.dz


def _interior_overlap(left: BoundingBox, right: BoundingBox) -> bool:
    return all(
        min(left.to_xb()[axis + 1], right.to_xb()[axis + 1])
        - max(left.to_xb()[axis], right.to_xb()[axis])
        > _NUMERIC_TOLERANCE_M
        for axis in (0, 2, 4)
    )


def _contains_strict(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        inner.xmin > outer.xmin + _NUMERIC_TOLERANCE_M
        and inner.xmax < outer.xmax - _NUMERIC_TOLERANCE_M
        and inner.ymin > outer.ymin + _NUMERIC_TOLERANCE_M
        and inner.ymax < outer.ymax - _NUMERIC_TOLERANCE_M
        and inner.zmin > outer.zmin + _NUMERIC_TOLERANCE_M
        and inner.zmax < outer.zmax - _NUMERIC_TOLERANCE_M
    )


def _within(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        inner.xmin >= outer.xmin - _NUMERIC_TOLERANCE_M
        and inner.xmax <= outer.xmax + _NUMERIC_TOLERANCE_M
        and inner.ymin >= outer.ymin - _NUMERIC_TOLERANCE_M
        and inner.ymax <= outer.ymax + _NUMERIC_TOLERANCE_M
        and inner.zmin >= outer.zmin - _NUMERIC_TOLERANCE_M
        and inner.zmax <= outer.zmax + _NUMERIC_TOLERANCE_M
    )


def _lattice_index(
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
        or abs(float(value) - (origin + index * spacing)) > _NUMERIC_TOLERANCE_M
    ):
        raise ValueError(f"{label} must align with the verified coarse-grid lattice")
    return index


def _normalize_axis_interval(
    lower: int,
    upper: int,
    total: int,
    axis_name: str,
) -> tuple[int, int, list[str]]:
    """Expand an interval so every generated 3D mesh has at least two cells per axis."""

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

    # A one-cell residual shell creates an FDS mesh that is effectively 2D and
    # can fail pressure-solver initialization when mixed with 3D meshes.
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


def _bounds_from_indices(
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


def _split_coarse_block(
    block: tuple[int, int, int, int, int, int],
) -> list[tuple[int, int, int, int, int, int]]:
    ix0, ix1, iy0, iy1, iz0, iz1 = block
    counts = (ix1 - ix0, iy1 - iy0, iz1 - iz0)
    if min(counts) <= 0:
        return []
    if counts[0] * counts[1] * counts[2] <= _MAX_CELLS_PER_MESH:
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
    return [piece for item in pair for piece in _split_coarse_block(item)]


def _validate_base_mesh_lattice(
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
            zip(
                (domain.xmin, domain.ymin, domain.zmin),
                spacing,
                coarse_ijk,
            )
        ):
            _lattice_index(xb[2 * axis], origin, step, count, "Base MESH boundary")
            _lattice_index(
                xb[2 * axis + 1],
                origin,
                step,
                count,
                "Base MESH boundary",
            )
            actual = (xb[2 * axis + 1] - xb[2 * axis]) / ijk[axis]
            if abs(actual - step) > max(_NUMERIC_TOLERANCE_M, step * 1e-5):
                raise ValueError(
                    "Verified base MESH does not use one uniform coarse-grid lattice"
                )


def _validate_partition(domain: BoundingBox, meshes: list[MeshRegion]) -> None:
    for index, left in enumerate(meshes):
        if not _within(domain, left.bounds):
            raise ValueError(f"Mesh lies outside simulation domain: {left.id}")
        for right in meshes[index + 1 :]:
            if _interior_overlap(left.bounds, right.bounds):
                raise ValueError(f"Mesh interiors overlap: {left.id}, {right.id}")

    covered = sum(_box_volume(mesh.bounds) for mesh in meshes)
    domain_volume = _box_volume(domain)
    if abs(covered - domain_volume) > max(1e-8, domain_volume * 1e-8):
        raise ValueError("MeshPlan does not cover the simulation domain exactly")


def resolve_local_mesh_plan(
    base_text: str,
    bundle: Any,
    simulation_domain: BoundingBox,
    base_cell_size_m: float,
    request: LocalMeshPlanRequest,
) -> ResolvedLocalMeshPlan:
    """Resolve one explicit EV-local refinement region on the verified base lattice."""

    if not math.isfinite(base_cell_size_m) or base_cell_size_m <= 0.0:
        raise ValueError("Verified base cell size must be finite and positive")
    if request.source_vehicle_index >= len(bundle.vehicle_geometries):
        raise ValueError("LocalMeshPlan source_vehicle_index is out of range")

    geometry = bundle.vehicle_geometries[request.source_vehicle_index]
    if geometry.mode == "LEGACY":
        raise ValueError("LocalMeshPlan requires scientific vehicle geometry")
    if not _within(simulation_domain, request.local_region):
        raise ValueError("Local refinement region must remain inside simulation domain")
    if not _contains_strict(request.local_region, geometry.body_bounds):
        raise ValueError(
            "Local refinement region must strictly contain the resolved vehicle body"
        )

    coarse_ijk_list, _ = compute_mesh_grid(
        simulation_domain,
        cell_size=base_cell_size_m,
    )
    coarse_ijk = tuple(int(value) for value in coarse_ijk_list)
    spacing = (
        simulation_domain.dx / coarse_ijk[0],
        simulation_domain.dy / coarse_ijk[1],
        simulation_domain.dz / coarse_ijk[2],
    )
    _validate_base_mesh_lattice(base_text, simulation_domain, spacing, coarse_ijk)

    region = request.local_region
    indices = (
        _lattice_index(
            region.xmin,
            simulation_domain.xmin,
            spacing[0],
            coarse_ijk[0],
            "local_region.xmin",
        ),
        _lattice_index(
            region.xmax,
            simulation_domain.xmin,
            spacing[0],
            coarse_ijk[0],
            "local_region.xmax",
        ),
        _lattice_index(
            region.ymin,
            simulation_domain.ymin,
            spacing[1],
            coarse_ijk[1],
            "local_region.ymin",
        ),
        _lattice_index(
            region.ymax,
            simulation_domain.ymin,
            spacing[1],
            coarse_ijk[1],
            "local_region.ymax",
        ),
        _lattice_index(
            region.zmin,
            simulation_domain.zmin,
            spacing[2],
            coarse_ijk[2],
            "local_region.zmin",
        ),
        _lattice_index(
            region.zmax,
            simulation_domain.zmin,
            spacing[2],
            coarse_ijk[2],
            "local_region.zmax",
        ),
    )
    ix0, ix1, iy0, iy1, iz0, iz1 = indices
    nx, ny, nz = coarse_ijk

    boundary_adjustments: list[str] = []
    ix0, ix1, changes = _normalize_axis_interval(ix0, ix1, nx, "x")
    boundary_adjustments.extend(changes)
    iy0, iy1, changes = _normalize_axis_interval(iy0, iy1, ny, "y")
    boundary_adjustments.extend(changes)
    iz0, iz1, changes = _normalize_axis_interval(iz0, iz1, nz, "z")
    boundary_adjustments.extend(changes)

    coarse_blocks = [
        (0, ix0, 0, ny, 0, nz),
        (ix1, nx, 0, ny, 0, nz),
        (ix0, ix1, 0, iy0, 0, nz),
        (ix0, ix1, iy1, ny, 0, nz),
        (ix0, ix1, iy0, iy1, 0, iz0),
        (ix0, ix1, iy0, iy1, iz1, nz),
    ]
    coarse_parts = [
        part
        for block in coarse_blocks
        for part in _split_coarse_block(block)
    ]

    meshes: list[MeshRegion] = []
    for index, block in enumerate(sorted(coarse_parts), start=1):
        meshes.append(
            MeshRegion(
                id=f"P4B_COARSE_{index:03d}",
                role="COARSE",
                bounds=_bounds_from_indices(simulation_domain, spacing, block),
                ijk=(
                    block[1] - block[0],
                    block[3] - block[2],
                    block[5] - block[4],
                ),
                cell_size_xyz_m=spacing,
            )
        )

    local_counts = (ix1 - ix0, iy1 - iy0, iz1 - iz0)
    local_ijk = tuple(count * request.refinement_ratio for count in local_counts)
    local_cells = local_ijk[0] * local_ijk[1] * local_ijk[2]
    if local_cells > _MAX_CELLS_PER_MESH:
        raise ValueError(
            f"Local refined mesh has {local_cells:,} cells; "
            f"limit is {_MAX_CELLS_PER_MESH:,} for P4b1"
        )
    local_bounds = _bounds_from_indices(
        simulation_domain, spacing, (ix0, ix1, iy0, iy1, iz0, iz1)
    )
    local_spacing = tuple(value / request.refinement_ratio for value in spacing)
    local_id = f"P4B_LOCAL_V{request.source_vehicle_index}"
    meshes.append(
        MeshRegion(
            id=local_id,
            role="LOCAL_REFINED",
            bounds=local_bounds,
            ijk=local_ijk,
            cell_size_xyz_m=local_spacing,
        )
    )
    _validate_partition(simulation_domain, meshes)

    return ResolvedLocalMeshPlan(
        source_vehicle_index=request.source_vehicle_index,
        simulation_domain=simulation_domain,
        requested_local_region=request.local_region,
        local_region=local_bounds,
        refinement_ratio=request.refinement_ratio,
        coarse_cell_size_xyz_m=spacing,
        local_cell_size_xyz_m=local_spacing,
        local_mesh_id=local_id,
        meshes=meshes,
        total_cells=sum(mesh.total_cells for mesh in meshes),
        boundary_adjustments=boundary_adjustments,
    )
