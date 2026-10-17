"""BoundingBox pure value object with no domain dependencies."""

from __future__ import annotations

import math
from typing import List
from pydantic import BaseModel, model_validator


class BoundingBox(BaseModel):
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float

    @model_validator(mode="after")
    def valid_bounds(self):
        if not all(math.isfinite(v) for v in self.to_xb()):
            raise ValueError("Bounds must be finite")
        if self.xmax <= self.xmin or self.ymax <= self.ymin or self.zmax <= self.zmin:
            raise ValueError("Bounds must have positive extents")
        return self

    @property
    def dx(self) -> float:
        return max(0.0, self.xmax - self.xmin)

    @property
    def dy(self) -> float:
        return max(0.0, self.ymax - self.ymin)

    @property
    def dz(self) -> float:
        return max(0.0, self.zmax - self.zmin)

    @property
    def volume(self) -> float:
        return self.dx * self.dy * self.dz

    def to_xb(self) -> List[float]:
        return [self.xmin, self.xmax, self.ymin, self.ymax, self.zmin, self.zmax]

    def contains_point(self, x: float, y: float, z: float, tol: float = 1e-4) -> bool:
        return (
            (self.xmin - tol <= x <= self.xmax + tol)
            and (self.ymin - tol <= y <= self.ymax + tol)
            and (self.zmin - tol <= z <= self.zmax + tol)
        )

    def intersects(self, other: BoundingBox, tol: float = 1e-4) -> bool:
        return not (
            self.xmax < other.xmin - tol
            or self.xmin > other.xmax + tol
            or self.ymax < other.ymin - tol
            or self.ymin > other.ymax + tol
            or self.zmax < other.zmin - tol
            or self.zmin > other.zmax + tol
        )
