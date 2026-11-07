"""Machine-readable source-local metrics for Local MeshPlan."""

from __future__ import annotations

import math
from typing import Any

from .mesh_metrics import calculate_d_star, ev_peak_hrr_evidence
from .mesh_plan_models import ResolvedLocalMeshPlan


def local_mesh_evidence(
    bundle: Any,
    plan: ResolvedLocalMeshPlan,
) -> dict[str, Any]:
    """Report local resolution without issuing scientific mesh-adequacy PASS."""

    index = plan.source_vehicle_index
    geometry = bundle.vehicle_geometries[index]
    selection = bundle.ev_selections[index]
    local = plan.local_mesh()
    hrr = ev_peak_hrr_evidence(selection)
    peak_hrr_kw = float(hrr["peak_hrr_kw"])
    if not math.isfinite(peak_hrr_kw) or peak_hrr_kw <= 0.0:
        raise ValueError("LocalMeshPlan requires a finite positive source peak HRR")

    max_local_spacing = max(local.cell_size_xyz_m)
    d_star = calculate_d_star(peak_hrr_kw)
    result: dict[str, Any] = {
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
        "dx_local_m": max_local_spacing,
        "d_star_m": d_star,
        "d_star_over_dx_local": d_star / max_local_spacing,
        "d_star_denominator": "MAX_LOCAL_CELL_SPACING",
        "local_source_mesh_resolved": True,
        "grid_sensitivity_required": True,
        **hrr,
    }
    if geometry.ground_clearance_m is not None:
        result["ground_clearance_m"] = geometry.ground_clearance_m
        result["ground_clearance_over_dz_local"] = (
            geometry.ground_clearance_m / local.cell_size_xyz_m[2]
        )
    if geometry.battery_bounds is not None:
        thickness = geometry.battery_bounds.dz
        result["battery_thickness_m"] = thickness
        result["battery_thickness_over_dz_local"] = (
            thickness / local.cell_size_xyz_m[2]
        )
    return result
