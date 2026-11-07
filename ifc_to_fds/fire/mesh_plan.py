"""Scenario-owned local mesh planning for EV fire source refinement.

The verified base remains the geometry source of truth. A LocalMeshPlan replaces
only FDS MESH records during scenario composition. Refined and coarse meshes are
adjacent, never overlapping.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.fire.mesh_metrics import calculate_d_star, ev_peak_hrr_evidence
from ifc_to_fds.mapping.exporter import compute_mesh_grid
from ifc_to_fds.validation.parser import parse_fds

_NUMERIC_TOLERANCE_M = 2e-6
_MAX_CELLS_PER_MESH = 500_000


class LocalMeshPlanRequest(BaseModel):
    """Explicit scenario request for one source-local refinement region."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    source_vehicle_index: int = Field(default=0, ge=0)
    local_region: BoundingBox
    refinement_ratio: int = Field(ge=2)


class MeshRegion(BaseModel):
    """One non-overlapping FDS mesh in a resolved scenario MeshPlan."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str
    role: Literal["COARSE", "LOCAL_REFINED"]
    bounds: BoundingBox
    ijk: tuple[int, int, int]
    cell_size_xyz_m: tuple[float, float, float]

    @model_validator(mode="after")
    def validate_region(self) -> "MeshRegion":
        if any(value <= 0 for value in self.ijk):
            raise ValueError("Mesh IJK must contain positive integers")
        if any(not math.isfinite(value) or value <= 0.0 for value in self.cell_size_xyz_m):
            raise ValueError("Mesh cell sizes must be finite and positive")
        return self

    @property
    def total_cells(self) -> int:
        return self.ijk[0] * self.ijk[1] * self.ijk[2]


class ResolvedLocalMeshPlan(BaseModel):
    """Deterministic, source-local, non-overlapping scenario mesh layout."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    source_vehicle_index: int
    simulation_domain: BoundingBox
    requested_local_region: BoundingBox
    local_region: BoundingBox
    refinement_ratio: int
    coarse_cell_size_xyz_m: tuple[float, float, float]
    local_cell_size_xyz_m: tuple[float, float, float]
    local_mesh_id: str
    meshes: list[MeshRegion]
    total_cells: int
    layout_method: Literal["ADJACENT_SHELL_REFINEMENT_V1"] = (
        "ADJACENT_SHELL_REFINEMENT_V1"
    )

    def local_mesh(self) -> MeshRegion:
        matches = [mesh for mesh in self.meshes if mesh.id == self.local_mesh_id]
        if len(matches) != 1:
            raise ValueError("Resolved LocalMeshPlan must contain exactly one local mesh")
        return matches[0]


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
        raise ValueError(
            f"{label} must align with the verified coarse-grid lattice"
        )
    return index


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
    """Split a lattice block without changing the verified coarse spacing."""

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


def _validate_partition(
    domain: BoundingBox,
    meshes: list[MeshRegion],
) -> None:
    for index, left in enumerate(meshes):
        if not _within(domain, left.bounds):
            raise ValueError(f"Mesh lies outside simulation domain: {left.id}")
        for right in meshes[index + 1 :]:
            if _interior_overlap(left.bounds, right.bounds):
                raise ValueError(f"Mesh interiors overlap: {left.id}, {right.id}")

    covered = sum(_box_volume(mesh.bounds) for mesh in meshes)
    if abs(covered - _box_volume(domain)) > max(
        1e-8, _box_volume(domain) * 1e-8
    ):
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
    ix0 = _lattice_index(region.xmin, simulation_domain.xmin, spacing[0], coarse_ijk[0], "local_region.xmin")
    ix1 = _lattice_index(region.xmax, simulation_domain.xmin, spacing[0], coarse_ijk[0], "local_region.xmax")
    iy0 = _lattice_index(region.ymin, simulation_domain.ymin, spacing[1], coarse_ijk[1], "local_region.ymin")
    iy1 = _lattice_index(region.ymax, simulation_domain.ymin, spacing[1], coarse_ijk[1], "local_region.ymax")
    iz0 = _lattice_index(region.zmin, simulation_domain.zmin, spacing[2], coarse_ijk[2], "local_region.zmin")
    iz1 = _lattice_index(region.zmax, simulation_domain.zmin, spacing[2], coarse_ijk[2], "local_region.zmax")

    nx, ny, nz = coarse_ijk
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
        bounds = _bounds_from_indices(simulation_domain, spacing, block)
        counts = (
            block[1] - block[0],
            block[3] - block[2],
            block[5] - block[4],
        )
        meshes.append(
            MeshRegion(
                id=f"P4B_COARSE_{index:03d}",
                role="COARSE",
                bounds=bounds,
                ijk=counts,
                cell_size_xyz_m=spacing,
            )
        )

    local_coarse_counts = (ix1 - ix0, iy1 - iy0, iz1 - iz0)
    local_ijk = tuple(
        count * request.refinement_ratio for count in local_coarse_counts
    )
    local_cells = local_ijk[0] * local_ijk[1] * local_ijk[2]
    if local_cells > _MAX_CELLS_PER_MESH:
        raise ValueError(
            f"Local refined mesh has {local_cells:,} cells; "
            f"limit is {_MAX_CELLS_PER_MESH:,} for P4b1"
        )
    local_bounds = _bounds_from_indices(
        simulation_domain,
        spacing,
        (ix0, ix1, iy0, iy1, iz0, iz1),
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
    )


def _format_values(values: list[float]) -> str:
    return ",".join(
        str(int(value)) if float(value).is_integer() else format(float(value), ".17g")
        for value in values
    )


def apply_local_mesh_plan(base_text: str, plan: ResolvedLocalMeshPlan) -> str:
    """Replace base MESH records by source spans, never by regex post-processing."""

    parsed = parse_fds(base_text)
    if parsed.errors or parsed.unsupported:
        raise ValueError("Cannot replace MESH records in invalid verified base")
    records = [record for record in parsed.records if record.kind == "MESH"]
    if not records or any(record.text_span is None for record in records):
        raise ValueError("Verified base MESH records have no source spans")

    rendered = "\n".join(
        (
            f"&MESH ID='{mesh.id}', "
            f"IJK={mesh.ijk[0]},{mesh.ijk[1]},{mesh.ijk[2]}, "
            f"XB={_format_values(mesh.bounds.to_xb())} /"
        )
        for mesh in plan.meshes
    )

    spans = sorted(record.text_span for record in records if record.text_span)
    chunks: list[str] = []
    cursor = 0
    for index, (start, stop) in enumerate(spans):
        chunks.append(base_text[cursor:start])
        if index == 0:
            chunks.append(rendered)
        cursor = stop
    chunks.append(base_text[cursor:])
    result = "".join(chunks)

    checked = parse_fds(result)
    if checked.errors or checked.unsupported:
        raise ValueError(
            f"Resolved LocalMeshPlan produced invalid FDS: "
            f"{checked.errors + checked.unsupported}"
        )
    emitted = [record for record in checked.records if record.kind == "MESH"]
    if [record.id for record in emitted] != [mesh.id for mesh in plan.meshes]:
        raise ValueError("Resolved LocalMeshPlan MESH identity differs after serialization")
    return result


def local_mesh_evidence(
    bundle: Any,
    plan: ResolvedLocalMeshPlan,
) -> dict[str, Any]:
    """Build machine-readable source-local mesh metrics without issuing adequacy PASS."""

    index = plan.source_vehicle_index
    geometry = bundle.vehicle_geometries[index]
    selection = bundle.ev_selections[index]
    local = plan.local_mesh()
    hrr = ev_peak_hrr_evidence(selection)
    peak_hrr_kw = float(hrr["peak_hrr_kw"])
    if not math.isfinite(peak_hrr_kw) or peak_hrr_kw <= 0.0:
        raise ValueError("LocalMeshPlan requires a finite positive source peak HRR")

    dx_local = max(local.cell_size_xyz_m)
    d_star = calculate_d_star(peak_hrr_kw)
    evidence: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "INCONCLUSIVE",
        "scientific_interpretation": "LOCAL_LAYOUT_SOFTWARE_VERIFIED_ONLY",
        "source_vehicle_index": index,
        "local_mesh_id": local.id,
        "layout_method": plan.layout_method,
        "refinement_ratio": plan.refinement_ratio,
        "mesh_count": len(plan.meshes),
        "total_cells": plan.total_cells,
        "local_region": plan.local_region.model_dump(),
        "coarse_cell_size_xyz_m": list(plan.coarse_cell_size_xyz_m),
        "local_cell_size_xyz_m": list(plan.local_cell_size_xyz_m),
        "dx_local_m": dx_local,
        "d_star_m": d_star,
        "d_star_over_dx_local": d_star / dx_local,
        "local_source_mesh_resolved": True,
        "grid_sensitivity_required": True,
        **hrr,
    }
    if geometry.ground_clearance_m is not None:
        evidence["ground_clearance_m"] = geometry.ground_clearance_m
        evidence["ground_clearance_over_dz_local"] = (
            geometry.ground_clearance_m / local.cell_size_xyz_m[2]
        )
    if geometry.battery_bounds is not None:
        thickness = geometry.battery_bounds.dz
        evidence["battery_thickness_m"] = thickness
        evidence["battery_thickness_over_dz_local"] = (
            thickness / local.cell_size_xyz_m[2]
        )
    return evidence


__all__ = [
    "LocalMeshPlanRequest",
    "MeshRegion",
    "ResolvedLocalMeshPlan",
    "apply_local_mesh_plan",
    "local_mesh_evidence",
    "resolve_local_mesh_plan",
]
