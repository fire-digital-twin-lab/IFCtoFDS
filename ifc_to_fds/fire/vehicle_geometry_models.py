"""Typed domain objects for reviewed EV vehicle and battery geometry."""

from __future__ import annotations

import math
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ifc_to_fds.domain.bim.bounding_box import BoundingBox

VehicleGeometryMode = Literal["LEGACY", "PARAMETRIC", "IFC_BOUND"]


class BatteryPack(BaseModel):
    """Explicit battery-pack geometry or an IFC-bound battery entity."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)

    source_entity_key: Optional[str] = Field(default=None, min_length=1)
    dimensions: Optional[Tuple[float, float, float]] = None
    center_offset_m: Optional[Tuple[float, float, float]] = None

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(
        cls, value: Optional[Tuple[float, float, float]]
    ) -> Optional[Tuple[float, float, float]]:
        if value is not None and (
            len(value) != 3 or any(d <= 0.0 or not math.isfinite(d) for d in value)
        ):
            raise ValueError("Battery dimensions must contain three finite positive values")
        return value

    @field_validator("center_offset_m")
    @classmethod
    def validate_offset(
        cls, value: Optional[Tuple[float, float, float]]
    ) -> Optional[Tuple[float, float, float]]:
        if value is not None and (
            len(value) != 3 or any(not math.isfinite(v) for v in value)
        ):
            raise ValueError("Battery center_offset_m must contain three finite values")
        return value

    @model_validator(mode="after")
    def validate_binding_mode(self) -> "BatteryPack":
        is_bound = self.source_entity_key is not None
        has_parametric = self.dimensions is not None or self.center_offset_m is not None
        if is_bound and has_parametric:
            raise ValueError(
                "Battery geometry must use either source_entity_key or parametric dimensions, not both"
            )
        if not is_bound and (
            self.dimensions is None or self.center_offset_m is None
        ):
            raise ValueError(
                "Parametric battery geometry requires both dimensions and center_offset_m"
            )
        return self


class VehicleGeometry(BaseModel):
    """Resolved vehicle geometry used by the scenario emitter and evidence bundle."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: VehicleGeometryMode
    source_entity_key: Optional[str] = None
    body_bounds: BoundingBox
    floor_z_m: Optional[float] = None
    ground_clearance_m: Optional[float] = None
    battery_bounds: Optional[BoundingBox] = None
    battery_source_entity_key: Optional[str] = None
    body_from_verified_base: bool = False
    provenance: Dict[str, Any] = Field(default_factory=dict)
