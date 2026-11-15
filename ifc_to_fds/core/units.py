"""Project length units; IfcOpenShell geometry is already in metres."""

import math
import ifcopenshell.util.unit


def _resolves_to_si_metre(unit):
    """True when the unit is SI length, or a conversion chain that ends in SI length."""
    for _ in range(8):
        if unit is None:
            return False
        if unit.is_a("IfcSIUnit"):
            return unit.UnitType == "LENGTHUNIT" and unit.Name == "METRE"
        if not unit.is_a("IfcConversionBasedUnit"):
            return False  # IfcContextDependentUnit and others have no defined factor
        unit = getattr(unit.ConversionFactor, "UnitComponent", None)
    return False


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
    if not _resolves_to_si_metre(unit):
        raise ValueError(
            f"Project LENGTHUNIT {getattr(unit, 'Name', unit.is_a())!r} "
            "cannot be converted to metres through SI units"
        )
    scale = float(ifcopenshell.util.unit.calculate_unit_scale(ifc_file))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid IFC length scale")
    return f"{getattr(unit, 'Prefix', '') or ''}{unit.Name}", scale
