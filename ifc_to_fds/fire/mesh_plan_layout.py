"""Deterministic non-overlapping layout resolver for Local MeshPlan."""

from __future__ import annotations

import math
from typing import Any

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.mapping.exporter import compute_mesh_grid

from .mesh_plan_grid import (
    MAX_CELLS_PER_MESH,
    bounds_from_indices,
    contains_strict,
    lattice_index,
    normalize_axis_interval,
    split_coarse_block,
    validate_base_mesh_lattice,
    validate_partition,
    within,
)
from .mesh_plan_models import LocalMeshPlanRequest, MeshRegion, ResolvedLocalMeshPlan


def _requested_indices(
    region: BoundingBox,
    domain: BoundingBox,
    spacing: tuple[float, float, float],
    coarse_ijk: tuple[int, int, int],
) -> tuple[int, int, int, int, int, int]:
    return (
        lattice_index(
            region.xmin, domain.xmin, spacing[0], coarse_ijk[0], "local_region.xmin"
        ),
        lattice_index(
            region.xmax, domain.xmin, spacing[0], coarse_ijk[0], "local_region.xmax"
        ),
        lattice_index(
            region.ymin, domain.ymin, spacing[1], coarse_ijk[1], "local_region.ymin"
        ),
        lattice_index(
            region.ymax, domain.ymin, spacing[1], coarse_ijk[1], "local_region.ymax"
        ),
        lattice_index(
            region.zmin, domain.zmin, spacing[2], coarse_ijk[2], "local_region.zmin"
        ),
        lattice_index(
            region.zmax, domain.zmin, spacing[2], coarse_ijk[2], "local_region.zmax"
        ),
    )


def _effective_indices(
    requested: tuple[int, int, int, int, int, int],
    coarse_ijk: tuple[int, int, int],
) -> tuple[tuple[int, int, int, int, int, int], list[str]]:
    ix0, ix1, iy0, iy1, iz0, iz1 = requested
    nx, ny, nz = coarse_ijk
    adjustments: list[str] = []

    ix0, ix1, changes = normalize_axis_interval(ix0, ix1, nx, "x")
    adjustments.extend(changes)
    iy0, iy1, changes = normalize_axis_interval(iy0, iy1, ny, "y")
    adjustments.extend(changes)
    iz0, iz1, changes = normalize_axis_interval(iz0, iz1, nz, "z")
    adjustments.extend(changes)
    return (ix0, ix1, iy0, iy1, iz0, iz1), adjustments


def _coarse_shell_blocks(
    indices: tuple[int, int, int, int, int, int],
    coarse_ijk: tuple[int, int, int],
) -> list[tuple[int, int, int, int, int, int]]:
    ix0, ix1, iy0, iy1, iz0, iz1 = indices
    nx, ny, nz = coarse_ijk
    logical_blocks = [
        (0, ix0, 0, ny, 0, nz),
        (ix1, nx, 0, ny, 0, nz),
        (ix0, ix1, 0, iy0, 0, nz),
        (ix0, ix1, iy1, ny, 0, nz),
        (ix0, ix1, iy0, iy1, 0, iz0),
        (ix0, ix1, iy0, iy1, iz1, nz),
    ]
    return [
        part
        for block in logical_blocks
        for part in split_coarse_block(block)
    ]


def _coarse_regions(
    domain: BoundingBox,
    spacing: tuple[float, float, float],
    blocks: list[tuple[int, int, int, int, int, int]],
) -> list[MeshRegion]:
    regions: list[MeshRegion] = []
    for index, block in enumerate(sorted(blocks), start=1):
        regions.append(
            MeshRegion(
                id=f"P4B_COARSE_{index:03d}",
                role="COARSE",
                bounds=bounds_from_indices(domain, spacing, block),
                ijk=(
                    block[1] - block[0],
                    block[3] - block[2],
                    block[5] - block[4],
                ),
                cell_size_xyz_m=spacing,
            )
        )
    return regions


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
    if not within(simulation_domain, request.local_region):
        raise ValueError("Local refinement region must remain inside simulation domain")
    if not contains_strict(request.local_region, geometry.body_bounds):
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
    validate_base_mesh_lattice(
        base_text,
        simulation_domain,
        spacing,
        coarse_ijk,
    )

    requested = _requested_indices(
        request.local_region,
        simulation_domain,
        spacing,
        coarse_ijk,
    )
    effective, boundary_adjustments = _effective_indices(requested, coarse_ijk)
    ix0, ix1, iy0, iy1, iz0, iz1 = effective

    meshes = _coarse_regions(
        simulation_domain,
        spacing,
        _coarse_shell_blocks(effective, coarse_ijk),
    )

    local_counts = (ix1 - ix0, iy1 - iy0, iz1 - iz0)
    local_ijk = tuple(
        count * request.refinement_ratio for count in local_counts
    )
    local_cells = local_ijk[0] * local_ijk[1] * local_ijk[2]
    if local_cells > MAX_CELLS_PER_MESH:
        raise ValueError(
            f"Local refined mesh has {local_cells:,} cells; "
            f"limit is {MAX_CELLS_PER_MESH:,} for P4b1"
        )

    local_bounds = bounds_from_indices(
        simulation_domain,
        spacing,
        effective,
    )
    local_spacing = tuple(
        value / request.refinement_ratio for value in spacing
    )
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
    validate_partition(simulation_domain, meshes)

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
