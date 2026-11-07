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

_ORIENTATION_TOLERANCE = 1e-6


def _confirmed_axis_aligned_yaw(placement: Any) -> float:
    """Resolve reviewed IFC yaw only when provenance proves a world-axis-aligned frame."""

    if not isinstance(placement, dict) or placement.get("status") != "CONFIRMED":
        raise ValueError(
            "IFC_BOUND vehicle requires CONFIRMED source placement provenance"
        )
    if placement.get("mapped_items"):
        raise ValueError(
            "IFC_BOUND vehicle orientation with mapped-item transforms is not yet supported"
        )

    values = placement.get("effective_world")
    if (
        not isinstance(values, (list, tuple))
        or len(values) != 16
        or any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values)
    ):
        raise ValueError(
            "IFC_BOUND vehicle requires a finite 4x4 effective_world placement matrix"
        )

    matrix = [[float(values[row * 4 + col]) for col in range(4)] for row in range(4)]
    if any(
        abs(actual - expected) > _ORIENTATION_TOLERANCE
        for actual, expected in zip(matrix[3], (0.0, 0.0, 0.0, 1.0))
    ):
        raise ValueError("IFC_BOUND vehicle placement is not a rigid homogeneous transform")

    rotation = [row[:3] for row in matrix[:3]]
    columns = [[rotation[row][col] for row in range(3)] for col in range(3)]
    for index, column in enumerate(columns):
        norm = math.sqrt(sum(value * value for value in column))
        if abs(norm - 1.0) > _ORIENTATION_TOLERANCE:
            raise ValueError(
                f"IFC_BOUND vehicle placement axis {index} is not unit length"
            )
    for left in range(3):
        for right in range(left + 1, 3):
            dot = sum(columns[left][axis] * columns[right][axis] for axis in range(3))
            if abs(dot) > _ORIENTATION_TOLERANCE:
                raise ValueError("IFC_BOUND vehicle placement axes are not orthogonal")

    determinant = (
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
    )
    if abs(determinant - 1.0) > _ORIENTATION_TOLERANCE:
        raise ValueError("IFC_BOUND vehicle placement must be a proper rotation")

    if any(
        abs(actual - expected) > _ORIENTATION_TOLERANCE
        for actual, expected in (
            (rotation[0][2], 0.0),
            (rotation[1][2], 0.0),
            (rotation[2][0], 0.0),
            (rotation[2][1], 0.0),
            (rotation[2][2], 1.0),
        )
    ):
        raise ValueError(
            "IFC_BOUND vehicle tilt is unsupported; oriented GEOM evidence is required"
        )

    yaw = math.atan2(rotation[1][0], rotation[0][0])
    quarter_turn = round(yaw / (math.pi / 2.0))
    expected_yaw = quarter_turn * (math.pi / 2.0)
    cos_yaw = math.cos(expected_yaw)
    sin_yaw = math.sin(expected_yaw)
    expected_rotation = (
        (cos_yaw, -sin_yaw, 0.0),
        (sin_yaw, cos_yaw, 0.0),
        (0.0, 0.0, 1.0),
    )
    if any(
        abs(rotation[row][col] - expected_rotation[row][col]) > _ORIENTATION_TOLERANCE
        for row in range(3)
        for col in range(3)
    ):
        raise ValueError(
            "IFC_BOUND vehicle yaw is not world-axis-aligned; GEOM vehicle support is required"
        )

    return float((quarter_turn % 4) * 90)


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
            orientation_status="UNVERIFIED",
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
            orientation_status="PARAMETRIC_WORLD_ALIGNED",
            yaw_degrees=0.0,
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

    yaw_degrees = _confirmed_axis_aligned_yaw(decision.placement)

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
        orientation_status="IFC_AXIS_ALIGNED_CONFIRMED",
        yaw_degrees=yaw_degrees,
        source_ifc_type=decision.source_ifc_type,
        source_type_class=decision.source_type_class,
        provenance={
            "geometry_semantics": "VERIFIED_MAPPING_BASE",
            "mapping_strategy": getattr(decision.strategy, "value", str(decision.strategy)),
            "simulation_role": decision.simulation_role,
            "semantic_role": semantic_role,
            "review_status": decision.review_status,
            "fds_representation": decision.fds_representation,
            "placement_status": decision.placement.get("status"),
            "orientation_method": "CONFIRMED_EFFECTIVE_WORLD_QUARTER_TURN",
        },
    )
