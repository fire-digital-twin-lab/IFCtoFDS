"""Typed domain models for scenario-owned Local MeshPlan."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ifc_to_fds.domain.bim.bounding_box import BoundingBox


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
        if any(
            not math.isfinite(value) or value <= 0.0
            for value in self.cell_size_xyz_m
        ):
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
            raise ValueError(
                "Resolved LocalMeshPlan must contain exactly one local mesh"
            )
        return matches[0]
