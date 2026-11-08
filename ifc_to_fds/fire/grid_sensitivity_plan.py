"""Resolve and serialize comparable P4c coarse/medium/fine mesh cases."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ifc_to_fds.domain.bim.bounding_box import BoundingBox

from .grid_sensitivity_models import (
    GridSensitivityCasePlan,
    GridSensitivityPlanRequest,
    ResolvedGridSensitivityPlan,
)
from .mesh_plan_layout import resolve_local_mesh_plan
from .mesh_plan_models import LocalMeshPlanRequest
from .mesh_plan_serialization import apply_local_mesh_plan


_LEVELS = ("COARSE", "MEDIUM", "FINE")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plan_digest(plan: Any) -> str:
    payload = json.dumps(
        plan.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def resolve_grid_sensitivity_plan(
    scenario_fds: str,
    bundle: Any,
    simulation_domain: BoundingBox,
    coarse_cell_size_m: float,
    request: GridSensitivityPlanRequest,
) -> ResolvedGridSensitivityPlan:
    """Build three comparable Local MeshPlans over one requested source region."""

    cases: list[GridSensitivityCasePlan] = []
    effective_region: dict[str, float] | None = None

    for level, ratio in zip(_LEVELS, request.refinement_ratios, strict=True):
        mesh_plan = resolve_local_mesh_plan(
            scenario_fds,
            bundle,
            simulation_domain,
            coarse_cell_size_m,
            LocalMeshPlanRequest(
                source_vehicle_index=request.source_vehicle_index,
                local_region=request.local_region,
                refinement_ratio=ratio,
            ),
        )
        region = mesh_plan.local_region.model_dump()
        if effective_region is None:
            effective_region = region
        elif region != effective_region:
            raise ValueError(
                "Grid-sensitivity cases resolved different effective local regions"
            )

        cases.append(
            GridSensitivityCasePlan(
                level=level,
                refinement_ratio=ratio,
                local_dx_m=max(mesh_plan.local_cell_size_xyz_m),
                mesh_plan_sha256=_plan_digest(mesh_plan),
                mesh_plan=mesh_plan,
            )
        )

    return ResolvedGridSensitivityPlan(
        source_vehicle_index=request.source_vehicle_index,
        requested_local_region=request.local_region,
        scenario_invariant_sha256=_sha256_text(scenario_fds),
        cases=cases,
    )


def render_grid_sensitivity_cases(
    scenario_fds: str,
    plan: ResolvedGridSensitivityPlan,
) -> dict[str, dict[str, Any]]:
    """Render case FDS while retaining a shared pre-mesh scenario fingerprint."""

    invariant = _sha256_text(scenario_fds)
    if invariant != plan.scenario_invariant_sha256:
        raise ValueError("Scenario changed after grid-sensitivity plan resolution")

    rendered: dict[str, dict[str, Any]] = {}
    for case in plan.cases:
        fds_text = apply_local_mesh_plan(scenario_fds, case.mesh_plan)
        rendered[case.level] = {
            "level": case.level,
            "refinement_ratio": case.refinement_ratio,
            "local_dx_m": case.local_dx_m,
            "mesh_plan_sha256": case.mesh_plan_sha256,
            "scenario_invariant_sha256": invariant,
            "fds_sha256": _sha256_text(fds_text),
            "fds_text": fds_text,
        }
    if len({item["fds_sha256"] for item in rendered.values()}) != 3:
        raise ValueError("Grid-sensitivity case FDS files must differ by mesh layout")
    return rendered
