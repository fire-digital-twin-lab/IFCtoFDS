"""Đối chiếu phép đổi tọa độ bản đồ do IFC khai báo khi ghép nguồn."""

import math

import numpy as np

from .placement import axis_placement_matrix
from .units import length_unit_scale


def declared_map_frame(file, project_scale):
    if file.schema == "IFC2X3":
        return None

    frame = None
    for operation in file.by_type("IfcCoordinateOperation"):
        source, target = operation.SourceCRS, operation.TargetCRS
        world = getattr(source, "WorldCoordinateSystem", None)
        if (
            not operation.is_a("IfcMapConversion")
            or world is None
            or target is None
            or not target.is_a("IfcProjectedCRS")
            or not (target.Name or "").strip()
        ):
            raise ValueError("IFC map frames require explicit source transforms for this CRS operation")

        map_scale = length_unit_scale(target.MapUnit) if target.MapUnit else project_scale
        offsets = np.asarray(
            [operation.Eastings, operation.Northings, operation.OrthogonalHeight],
            dtype=float,
        ) * map_scale
        a, b = operation.XAxisAbscissa, operation.XAxisOrdinate
        if a is None and b is None:
            a, b = 1.0, 0.0
        a, b = a or 0.0, b or 0.0
        norm = math.hypot(a, b)
        scale = 1.0 if operation.Scale is None else operation.Scale
        factors = np.asarray(
            [getattr(operation, "Factor" + axis, 1.0) for axis in "XYZ"], dtype=float
        )
        if not norm or not math.isfinite(norm) or not math.isfinite(scale) or scale <= 0:
            raise ValueError("IFC map frames have an invalid axis or scale")
        if not np.isfinite(factors).all() or np.any(factors <= 0) or not np.isfinite(offsets).all():
            raise ValueError("IFC map frames have an invalid offset or scale factor")

        c, s = a / norm, b / norm
        matrix = np.eye(4)
        matrix[:3, :3] = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]) * (
            factors * scale * map_scale / project_scale
        )
        matrix[:3, 3] = offsets
        wcs = axis_placement_matrix(world)
        wcs[:3, 3] *= project_scale
        placement = matrix @ np.linalg.inv(wcs)
        if not np.isfinite(placement).all():
            raise ValueError("IFC map frames produce a nonfinite transform in metres")
        current = target.Name.strip().casefold(), placement
        require_matching_map_frames(frame, current)
        frame = current
    return frame


def require_matching_map_frames(left, right):
    if left is not None and right is not None and (
        left[0] != right[0] or not np.allclose(left[1], right[1], atol=1e-8, rtol=0)
    ):
        raise ValueError("Conflicting IFC map frames require explicit source transforms")
