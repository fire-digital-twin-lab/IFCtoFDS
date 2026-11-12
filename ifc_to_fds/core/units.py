"""Project length units; IfcOpenShell geometry is already in metres."""

import math
from ifcopenshell.util.unit import get_prefix_multiplier


def length_unit_scale(unit):
    """Đổi đơn vị chiều dài đã khai báo sang mét qua chuỗi hệ số IFC."""
    seen = set()
    scale = 1.0
    while unit is not None and getattr(unit, "UnitType", None) == "LENGTHUNIT":
        if unit.is_a("IfcSIUnit") and unit.Name == "METRE":
            scale *= get_prefix_multiplier(unit.Prefix)
            if math.isfinite(scale) and scale > 0:
                return scale
            break
        dimensions = getattr(unit, "Dimensions", None)
        if (
            not unit.is_a("IfcConversionBasedUnit")
            or unit.id() in seen
            or dimensions is None
            or tuple(dimensions) != (1, 0, 0, 0, 0, 0, 0)
            or getattr(unit, "ConversionOffset", 0) != 0
        ):
            break
        seen.add(unit.id())
        factor = unit.ConversionFactor
        value = getattr(getattr(factor, "ValueComponent", None), "wrappedValue", None)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            break
        scale *= value
        unit = factor.UnitComponent
    raise ValueError("Invalid or unsupported IFC length unit conversion to SI metres")


def get_length_unit_scale(ifc_file):
    projects = ifc_file.by_type("IfcProject")
    assignment = getattr(projects[0], "UnitsInContext", None) if projects else None
    units = [
        u
        for u in getattr(assignment, "Units", ())
        if getattr(u, "UnitType", None) == "LENGTHUNIT"
    ]
    if len(units) != 1:
        raise ValueError(
            "Exactly one project LENGTHUNIT is required; metres cannot be assumed"
        )
    unit = units[0]
    return f"{getattr(unit, 'Prefix', '') or ''}{unit.Name}", length_unit_scale(unit)
