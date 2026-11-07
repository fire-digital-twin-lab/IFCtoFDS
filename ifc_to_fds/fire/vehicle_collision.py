"""Fail-closed collision gate between resolved vehicles and verified base geometry."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.domain.mapping import MappingPlan
from ifc_to_fds.fire.base_geometry import VerifiedBaseGeometry
from ifc_to_fds.fire.vehicle_geometry_models import VehicleGeometry
from ifc_to_fds.geometry.triangle_box import prove_mesh_clearance_from_box

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
    geom_aabb_separated_entities: int = Field(default=0, ge=0)
    geom_exact_checked_entities: int = Field(default=0, ge=0)
    geom_exact_primitive_checks: int = Field(default=0, ge=0)
    geom_exact_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    nearest_entity_key: Optional[str] = None
    minimum_aabb_clearance_m: Optional[float] = Field(default=None, ge=0)
    tolerance_m: float = _COLLISION_TOLERANCE_M
    method: str = "OBST_AABB_PLUS_SEALED_FDS_GEOM_EXACT_BINARY64_SAT"
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
    verified_base_geometry: Optional[VerifiedBaseGeometry] = None,
) -> List[VehicleCollisionAssessment]:
    """Require scientific vehicles to be separated from verified base solids.

    OBST uses its exact serialized AABB.

    GEOM first uses disjoint AABBs as a separation proof. If AABBs overlap or
    touch, PASS requires exact emitted GEOM reconstructed from the sealed FDS:
    every GEOM primitive must be separated from an outward-expanded vehicle box
    by exact binary64 triangle/AABB SAT plus a containment boolean. Missing or
    unavailable exact evidence remains fail-closed.
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
        geom_aabb_separated = 0
        geom_exact_checked = 0
        geom_exact_primitive_checks = 0
        geom_exact_evidence: List[Dict[str, Any]] = []
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

            if clearance > _COLLISION_TOLERANCE_M:
                if representation == "GEOM":
                    geom_aabb_separated += 1
                continue

            if representation == "OBST":
                raise ValueError(
                    "Vehicle collision/contact with verified base OBST: "
                    f"vehicle={index}, entity_key={decision.entity_key}, "
                    f"clearance_m={clearance:.6g}"
                )

            if verified_base_geometry is None:
                raise ValueError(
                    "Vehicle clearance against verified base GEOM is INCONCLUSIVE: "
                    f"vehicle={index}, entity_key={decision.entity_key}; "
                    "AABB overlaps/touches and sealed emitted GEOM evidence was not supplied"
                )

            meshes = verified_base_geometry.meshes_for(decision.entity_key)
            primitive_ids = verified_base_geometry.geom_primitive_ids.get(
                decision.entity_key, ()
            )
            if not meshes or len(meshes) != len(primitive_ids):
                raise ValueError(
                    "Vehicle clearance against verified base GEOM is INCONCLUSIVE: "
                    f"vehicle={index}, entity_key={decision.entity_key}; "
                    "sealed emitted GEOM evidence is incomplete"
                )

            geom_exact_checked += 1
            for primitive_id, mesh in zip(primitive_ids, meshes):
                geom_exact_primitive_checks += 1
                try:
                    evidence = prove_mesh_clearance_from_box(
                        mesh,
                        geometry.body_bounds,
                        _COLLISION_TOLERANCE_M,
                    )
                except (ValueError, RuntimeError) as exc:
                    raise ValueError(
                        "Vehicle clearance against verified base GEOM is INCONCLUSIVE: "
                        f"vehicle={index}, entity_key={decision.entity_key}, "
                        f"primitive_id={primitive_id}; exact geometry evidence unavailable: {exc}"
                    ) from exc
                item = {
                    "entity_key": decision.entity_key,
                    "primitive_id": primitive_id,
                    **evidence,
                }
                geom_exact_evidence.append(item)
                if evidence["status"] != "SEPARATED":
                    raise ValueError(
                        "Vehicle collision/contact or clearance violation with verified base GEOM: "
                        f"vehicle={index}, entity_key={decision.entity_key}, "
                        f"primitive_id={primitive_id}; evidence={evidence}"
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
                geom_aabb_separated_entities=geom_aabb_separated,
                geom_exact_checked_entities=geom_exact_checked,
                geom_exact_primitive_checks=geom_exact_primitive_checks,
                geom_exact_evidence=geom_exact_evidence,
                nearest_entity_key=nearest_key,
                minimum_aabb_clearance_m=minimum_clearance,
            )
        )

    return assessments


__all__ = [
    "VehicleCollisionAssessment",
    "assess_vehicle_base_collisions",
]
