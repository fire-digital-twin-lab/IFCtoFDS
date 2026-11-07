"""Fail-closed vehicle geometry contract for EV fire scenarios.

The legacy geometry path remains available for backward compatibility. Scientific
vehicle geometry must opt into PARAMETRIC or IFC_BOUND mode so source identity,
floor reference and underbody clearance are explicit and machine-readable.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

from ifc_to_fds.domain.bim.bounding_box import BoundingBox
from ifc_to_fds.domain.mapping import MappingPlan
from ifc_to_fds.fire.vehicle_geometry_models import (
    BatteryPack,
    VehicleGeometry,
    VehicleGeometryMode,
)

__all__ = [
    "BatteryPack",
    "VehicleGeometry",
    "VehicleGeometryMode",
    "resolve_vehicle_geometry",
]

_GEOMETRY_TOLERANCE_M = 1e-4

def _centered_bounds(
    position: Tuple[float, float, float],
    dimensions: Tuple[float, float, float],
) -> BoundingBox:
    cx, cy, cz = position
    dx, dy, dz = dimensions
    return BoundingBox(
        xmin=cx - dx / 2.0,
        xmax=cx + dx / 2.0,
        ymin=cy - dy / 2.0,
        ymax=cy + dy / 2.0,
        zmin=cz - dz / 2.0,
        zmax=cz + dz / 2.0,
    )


def _decision_bounds(mapping_plan: MappingPlan, entity_key: str, label: str) -> BoundingBox:
    decision = mapping_plan.get_decision(entity_key)
    if decision is None:
        raise ValueError(f"{label} source entity is not present in MappingPlan: {entity_key}")
    bounds = decision.representation_bounds or decision.element_bounds
    if bounds is None:
        raise ValueError(f"{label} source entity has no verified bounds: {entity_key}")
    return bounds


def _contains_box(outer: BoundingBox, inner: BoundingBox) -> bool:
    tol = _GEOMETRY_TOLERANCE_M
    return (
        inner.xmin >= outer.xmin - tol
        and inner.xmax <= outer.xmax + tol
        and inner.ymin >= outer.ymin - tol
        and inner.ymax <= outer.ymax + tol
        and inner.zmin >= outer.zmin - tol
        and inner.zmax <= outer.zmax + tol
    )


def _resolve_battery_bounds(
    battery: Optional[BatteryPack],
    mapping_plan: MappingPlan,
    body_bounds: BoundingBox,
) -> tuple[Optional[BoundingBox], Optional[str]]:
    if battery is None:
        return None, None

    if battery.source_entity_key is not None:
        decision = mapping_plan.get_decision(battery.source_entity_key)
        if decision is None:
            raise ValueError(
                f"Battery source entity is not present in MappingPlan: {battery.source_entity_key}"
            )
        semantic_role = str(
            (decision.decision or {}).get("semantic_role", "")
        ).strip().upper()
        if (
            str(decision.simulation_role).strip().upper() != "PASSIVE_OBSTACLE"
            or decision.review_status != "APPROVED"
            or semantic_role != "BATTERY_PACK"
        ):
            raise ValueError(
                "Battery source requires reviewed semantic_role=BATTERY_PACK "
                "with PASSIVE_OBSTACLE authorization"
            )
        bounds = decision.representation_bounds or decision.element_bounds
        if bounds is None:
            raise ValueError(
                f"Battery source entity has no verified bounds: {battery.source_entity_key}"
            )
        source_key = battery.source_entity_key
    else:
        assert battery.dimensions is not None
        assert battery.center_offset_m is not None
        body_center = (
            (body_bounds.xmin + body_bounds.xmax) / 2.0,
            (body_bounds.ymin + body_bounds.ymax) / 2.0,
            (body_bounds.zmin + body_bounds.zmax) / 2.0,
        )
        center = tuple(
            body_center[index] + battery.center_offset_m[index] for index in range(3)
        )
        bounds = _centered_bounds(center, battery.dimensions)
        source_key = None

    if not _contains_box(body_bounds, bounds):
        raise ValueError("Battery bounds must remain within the resolved vehicle body bounds")
    return bounds, source_key


def resolve_vehicle_geometry(
    selection: Any,
    mapping_plan: MappingPlan,
    dimensions: Tuple[float, float, float],
) -> VehicleGeometry:
    """Resolve a scenario vehicle without inventing scientific geometry.

    LEGACY preserves the historical center-based solid box and top burner.
    PARAMETRIC requires an explicit floor elevation and positive ground clearance.
    IFC_BOUND requires an explicit MappingPlan entity whose verified OBST bounds
    are reused from the accepted base model.
    """

    mode = str(getattr(selection, "geometry_mode", "LEGACY")).upper()
    if mode not in {"LEGACY", "PARAMETRIC", "IFC_BOUND"}:
        raise ValueError(f"Unsupported vehicle geometry mode: {mode}")

    position = tuple(float(v) for v in selection.position)
    if len(position) != 3 or any(not math.isfinite(v) for v in position):
        raise ValueError("Vehicle position must contain three finite coordinates")

    if mode == "LEGACY":
        body_bounds = _centered_bounds(position, dimensions)
        battery_bounds, battery_source = _resolve_battery_bounds(
            getattr(selection, "battery_geometry", None), mapping_plan, body_bounds
        )
        return VehicleGeometry(
            mode="LEGACY",
            source_entity_key=getattr(selection, "source_entity_key", None),
            body_bounds=body_bounds,
            battery_bounds=battery_bounds,
            battery_source_entity_key=battery_source,
            body_from_verified_base=False,
            provenance={"geometry_semantics": "LEGACY_CENTERED_BOX"},
        )

    floor_z = getattr(selection, "floor_z_m", None)
    if floor_z is None or not math.isfinite(float(floor_z)):
        raise ValueError(f"{mode} vehicle geometry requires finite floor_z_m")
    floor_z = float(floor_z)

    if mode == "PARAMETRIC":
        clearance = getattr(selection, "ground_clearance_m", None)
        if clearance is None or not math.isfinite(float(clearance)) or float(clearance) <= 0.0:
            raise ValueError(
                "PARAMETRIC vehicle geometry requires positive ground_clearance_m"
            )
        clearance = float(clearance)
        expected_center_z = floor_z + clearance + dimensions[2] / 2.0
        if abs(position[2] - expected_center_z) > _GEOMETRY_TOLERANCE_M:
            raise ValueError(
                "Vehicle position.z is inconsistent with floor_z_m, ground_clearance_m "
                "and vehicle height"
            )
        body_bounds = _centered_bounds(position, dimensions)
        actual_clearance = body_bounds.zmin - floor_z
        if actual_clearance <= _GEOMETRY_TOLERANCE_M:
            raise ValueError("Resolved vehicle body does not preserve positive ground clearance")
        battery_bounds, battery_source = _resolve_battery_bounds(
            getattr(selection, "battery_geometry", None), mapping_plan, body_bounds
        )
        return VehicleGeometry(
            mode="PARAMETRIC",
            source_entity_key=getattr(selection, "source_entity_key", None),
            body_bounds=body_bounds,
            floor_z_m=floor_z,
            ground_clearance_m=actual_clearance,
            battery_bounds=battery_bounds,
            battery_source_entity_key=battery_source,
            body_from_verified_base=False,
            provenance={"geometry_semantics": "EXPLICIT_PARAMETRIC"},
        )

    source_entity_key = getattr(selection, "source_entity_key", None)
    if not source_entity_key:
        raise ValueError("IFC_BOUND vehicle geometry requires source_entity_key")
    decision = mapping_plan.get_decision(source_entity_key)
    if decision is None:
        raise ValueError(
            f"Vehicle source entity is not present in MappingPlan: {source_entity_key}"
        )
    semantic_role = str((decision.decision or {}).get("semantic_role", "")).strip().upper()
    if (
        str(decision.simulation_role).strip().upper() != "PASSIVE_OBSTACLE"
        or decision.review_status != "APPROVED"
        or semantic_role != "VEHICLE"
    ):
        raise ValueError(
            "IFC_BOUND source requires reviewed semantic_role=VEHICLE "
            "with PASSIVE_OBSTACLE authorization"
        )
    if decision.fds_representation != "OBST":
        raise ValueError(
            "IFC_BOUND vehicle currently requires an OBST representation in the verified base"
        )
    body_bounds = decision.representation_bounds or decision.element_bounds
    if body_bounds is None:
        raise ValueError(f"Vehicle source entity has no verified bounds: {source_entity_key}")

    body_center = (
        (body_bounds.xmin + body_bounds.xmax) / 2.0,
        (body_bounds.ymin + body_bounds.ymax) / 2.0,
        (body_bounds.zmin + body_bounds.zmax) / 2.0,
    )
    if any(
        abs(position[index] - body_center[index]) > _GEOMETRY_TOLERANCE_M
        for index in range(3)
    ):
        raise ValueError(
            "IFC_BOUND vehicle position must match the verified source body center"
        )

    actual_clearance = body_bounds.zmin - floor_z
    if actual_clearance <= _GEOMETRY_TOLERANCE_M:
        raise ValueError(
            "IFC_BOUND vehicle source does not preserve positive ground clearance"
        )
    requested_clearance = getattr(selection, "ground_clearance_m", None)
    if requested_clearance is not None and (
        not math.isfinite(float(requested_clearance))
        or abs(float(requested_clearance) - actual_clearance) > _GEOMETRY_TOLERANCE_M
    ):
        raise ValueError(
            "IFC_BOUND ground_clearance_m does not match verified source geometry"
        )

    battery_bounds, battery_source = _resolve_battery_bounds(
        getattr(selection, "battery_geometry", None), mapping_plan, body_bounds
    )
    return VehicleGeometry(
        mode="IFC_BOUND",
        source_entity_key=source_entity_key,
        body_bounds=body_bounds,
        floor_z_m=floor_z,
        ground_clearance_m=actual_clearance,
        battery_bounds=battery_bounds,
        battery_source_entity_key=battery_source,
        body_from_verified_base=True,
        provenance={
            "geometry_semantics": "VERIFIED_MAPPING_BASE",
            "mapping_strategy": getattr(decision.strategy, "value", str(decision.strategy)),
            "simulation_role": decision.simulation_role,
            "semantic_role": semantic_role,
            "review_status": decision.review_status,
            "fds_representation": decision.fds_representation,
        },
    )
