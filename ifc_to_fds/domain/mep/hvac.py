"""Operational HVAC contracts, independent of IFC kernels and FDS text."""

import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


class EndpointSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    kind: Literal["AMBIENT", "VENT"]
    vent_xb: tuple[float, float, float, float, float, float] | None = None
    loss: tuple[float, float] = (1.0, 1.0)
    coordinate_frame: Literal["WORLD", "REBASED"] | None = None

    @model_validator(mode="after")
    def validate_boundary(self):
        if any(x < 0 for x in self.loss):
            raise ValueError("Endpoint losses must be nonnegative")
        if self.kind == "AMBIENT" and (self.vent_xb is not None or self.coordinate_frame is not None):
            raise ValueError("AMBIENT endpoint cannot have a CFD vent")
        if self.kind == "VENT":
            if self.vent_xb is None:
                raise ValueError("VENT endpoint requires vent_xb in model metres")
            spans = [self.vent_xb[i + 1] - self.vent_xb[i] for i in (0, 2, 4)]
            if sum(x == 0 for x in spans) != 1 or any(x < 0 for x in spans):
                raise ValueError("HVAC vent must be a positive-area axis-aligned rectangle")
        return self


class FittingSpec(BaseModel):
    """Tổn thất phụ kiện đã duyệt theo thứ tự cổng và tiết diện tham chiếu."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    kind: Literal["ELBOW", "REDUCER"]
    forward_port_keys: tuple[str, str]
    k: tuple[float, float]
    reference_areas_m2: tuple[float, float]
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fitting(self):
        if not self.source.strip() or not all(self.forward_port_keys) or len(set(self.forward_port_keys)) != 2:
            raise ValueError("Fitting requires loss evidence and two distinct forward ports")
        if any(k < 0 for k in self.k) or any(a <= 0 for a in self.reference_areas_m2):
            raise ValueError("Fitting losses must be nonnegative and reference areas positive")
        return self


class DuctSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    diameter_m: float | None = Field(None, gt=0)
    area_m2: float | None = Field(None, gt=0)
    perimeter_m: float | None = Field(None, gt=0)
    length_m: float | None = Field(None, gt=0)
    roughness_m: float = Field(0.0, ge=0)
    volume_flow_m3_s: float | None = None
    endpoints: dict[str, EndpointSpec] = Field(default_factory=dict)
    fitting: FittingSpec | None = None

    @model_serializer(mode="wrap")
    def serialize_spec(self, handler):
        data = handler(self)
        if self.fitting is None:
            data.pop("fitting", None)
        return data

    def fitting_loss(self):
        if self.fitting is None:
            return None
        area = self.area_m2 if self.diameter_m is None else math.pi / 4 * self.diameter_m**2
        if area is None or area <= 0 or not math.isfinite(area):
            raise ValueError("Fitting representative area must be positive and finite")
        # Bảo toàn Kρ(Q/A)²/2 cho cùng lưu lượng ở hai tiết diện tham chiếu.
        values = tuple(
            0.0 if coefficient == 0 else coefficient * (area / reference) ** 2
            for coefficient, reference in zip(self.fitting.k, self.fitting.reference_areas_m2)
        )
        if any(
            not math.isfinite(value) or (coefficient > 0 and value == 0)
            for coefficient, value in zip(self.fitting.k, values)
        ):
            raise ValueError("Fitting loss at representative area is not representable")
        return values

    @model_validator(mode="after")
    def validate_section(self):
        if self.diameter_m is not None:
            if self.area_m2 is not None or self.perimeter_m is not None:
                raise ValueError("Specify diameter OR area and perimeter")
        elif self.area_m2 is None or self.perimeter_m is None:
            raise ValueError("HVAC requires diameter_m or area_m2 and perimeter_m; AABB inference is disabled")
        elif self.perimeter_m**2 < 4 * math.pi * self.area_m2 * (1 - 1e-8):
            raise ValueError("Cross-sectional area and perimeter are inconsistent")
        if self.fitting is not None:
            if self.length_m is None or self.volume_flow_m3_s is not None:
                raise ValueError("Reviewed fitting requires measured length and passive flow")
            if self.fitting.kind == "REDUCER" and self.roughness_m != 0:
                raise ValueError("Reducer uses reviewed losses without representative-section friction")
            try:
                self.fitting_loss()
            except OverflowError as exc:
                raise ValueError("Fitting loss at representative area is not finite") from exc
        return self


class HvacNode(BaseModel):
    id: str
    port_keys: list[str]
    entity_keys: list[str]
    xyz: tuple[float, float, float]
    duct_ids: list[str]
    boundary: EndpointSpec | None = None


class HvacDuct(BaseModel):
    id: str
    entity_key: str
    node_ids: tuple[str, str]
    length_m: float
    spec: DuctSpec


class HvacNetworkPlan(BaseModel):
    nodes: list[HvacNode] = Field(default_factory=list)
    ducts: list[HvacDuct] = Field(default_factory=list)

    def assignments(self):
        result: dict[str, list[str]] = {}
        for duct in self.ducts:
            result.setdefault(duct.entity_key, []).append(duct.id)
        for node in self.nodes:
            ids = [node.id]
            if node.boundary and node.boundary.kind == "VENT":
                ids.append("V_" + node.id)
            for key in node.entity_keys:
                result.setdefault(key, []).extend(ids)
        return result
