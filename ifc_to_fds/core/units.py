"""Project length units; IfcOpenShell geometry is already in metres."""

import math
import ifcopenshell.util.unit


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
    scale = float(ifcopenshell.util.unit.calculate_unit_scale(ifc_file))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid IFC length scale")
    unit = units[0]
    return f"{getattr(unit, 'Prefix', '') or ''}{unit.Name}", scale
