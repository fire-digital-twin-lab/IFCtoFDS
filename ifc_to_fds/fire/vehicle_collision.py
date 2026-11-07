"""Fail-closed collision gate between resolved vehicles and verified base geometry."""

from __future__ import annotations

import math
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.domain.mapping import MappingPlan
from ifc_to_fds.fire.vehicle_geometry_models import VehicleGeometry

_COLLISION_TOLERANCE_M = 1e-4


class VehicleCollisionAssessment(BaseModel):
    """Machine-readable E2 evidence for base-geometry separation."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    vehicle_index: int = Field(ge=1)
    geometry_mode: Literal["PARAMETRIC", "IFC_BOUND"]
    source_entity_key: Optional[str] = None
    excluded_entity_keys: List[str] = Field(default_factory=list)
    checked_base_entities: int = Field(ge=0)
    checked_obst_entities: int = Field(ge=0)
    checked_geom_entities: int = Field(ge=0)
    nearest_entity_key: Optional[str] = None
    minimum_aabb_clearance_m: Optional[float] = Field(default=None, ge=0)
    tolerance_m: float = _COLLISION_TOLERANCE_M
    method: str = "AABB_SEPARATION_WITH_EXACT_OBST_AND_FAIL_CLOSED_GEOM"
    status: Literal["PASS"] = "PASS"


def _aabb_distance(left: BoundingBox, right: BoundingBox) -> float:
    """Return Euclidean separation between two axis-aligned bounding boxes."""

    dx = max(right.xmin - left.xmax, left.xmin - right.xmax, 0.0)
    dy = max(right.ymin - left.ymax, left.ymin - right.ymax, 0.0)
    dz = max(right.zmin - left.zmax, left.zmin - right.zmax, 0.0)
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def assess_vehicle_base_collisions(
    mapping_plan: MappingPlan,
    vehicle_geometries: List[VehicleGeometry],
) -> List[VehicleCollisionAssessment]:
    """Require scientific vehicles to be separated from verified base solids.

    For OBST, AABB is the actual serialized solid and distance <= tolerance is
    rejected as collision/contact. For GEOM, disjoint AABBs prove separation;
    overlapping/touching AABBs are fail-closed because exact mesh intersection
    evidence is not available in MappingPlan.
    """

    assessments: List[VehicleCollisionAssessment] = []

    for index, geometry in enumerate(vehicle_geometries, start=1):
        if geometry.mode == "LEGACY":
            continue

        excluded = {
            key
            for key in (
                geometry.source_entity_key,
                geometry.battery_source_entity_key,
            )
            if key
        }
        checked = 0
        checked_obst = 0
        checked_geom = 0
        nearest_key: Optional[str] = None
        minimum_clearance: Optional[float] = None

        for decision in mapping_plan.decisions:
            representation = str(decision.fds_representation).strip().upper()
            if representation not in {"OBST", "GEOM"}:
                continue
            if decision.entity_key in excluded:
                continue

            bounds = decision.representation_bounds or decision.element_bounds
            if bounds is None:
                raise ValueError(
                    "Verified base emitting entity has no bounds for collision gate: "
                    f"{decision.entity_key}"
                )

            checked += 1
            if representation == "OBST":
                checked_obst += 1
            else:
                checked_geom += 1

            clearance = _aabb_distance(geometry.body_bounds, bounds)
            if minimum_clearance is None or clearance < minimum_clearance:
                minimum_clearance = clearance
                nearest_key = decision.entity_key

            if clearance <= _COLLISION_TOLERANCE_M:
                if representation == "OBST":
                    raise ValueError(
                        "Vehicle collision/contact with verified base OBST: "
                        f"vehicle={index}, entity_key={decision.entity_key}, "
                        f"clearance_m={clearance:.6g}"
                    )
                raise ValueError(
                    "Vehicle clearance against verified base GEOM is INCONCLUSIVE: "
                    f"vehicle={index}, entity_key={decision.entity_key}; "
                    "AABB overlaps/touches and exact mesh collision evidence is required"
                )

        assessments.append(
            VehicleCollisionAssessment(
                vehicle_index=index,
                geometry_mode=geometry.mode,
                source_entity_key=geometry.source_entity_key,
                excluded_entity_keys=sorted(excluded),
                checked_base_entities=checked,
                checked_obst_entities=checked_obst,
                checked_geom_entities=checked_geom,
                nearest_entity_key=nearest_key,
                minimum_aabb_clearance_m=minimum_clearance,
            )
        )

    return assessments


__all__ = [
    "VehicleCollisionAssessment",
    "assess_vehicle_base_collisions",
]
