"""IFC Unit Assignment and Normalization.

Extracts unit scale factors from IfcUnitAssignment to ensure all dimensions,
coordinates, and bounding boxes are normalized to standard SI meters.
"""

from typing import Tuple
import ifcopenshell


PREFIX_MULTIPLIERS = {
    "EXA": 1e18,
    "PETA": 1e15,
    "TERA": 1e12,
    "GIGA": 1e9,
    "MEGA": 1e6,
    "KILO": 1e3,
    "HECTO": 1e2,
    "DECA": 1e1,
    "DECI": 1e-1,
    "CENTI": 1e-2,
    "MILLI": 1e-3,
    "MICRO": 1e-6,
    "NANO": 1e-9,
    "PICO": 1e-12,
    "FEMTO": 1e-15,
    "ATTO": 1e-18,
}


def get_length_unit_scale(ifc_file: ifcopenshell.file) -> Tuple[str, float]:
    """Returns (unit_name, scale_factor_to_meters) for the given IFC file."""
    for unit_assignment in ifc_file.by_type("IfcUnitAssignment"):
        for unit in getattr(unit_assignment, "Units", []):
            # 1. SI Unit
            if unit.is_a("IfcSIUnit"):
                unit_type = getattr(unit, "UnitType", "")
                if unit_type == "LENGTHUNIT":
                    name = getattr(unit, "Name", "METRE")
                    prefix = getattr(unit, "Prefix", None)
                    multiplier = PREFIX_MULTIPLIERS.get(prefix, 1.0) if prefix else 1.0
                    unit_name = f"{prefix}_{name}" if prefix else name
                    return unit_name, float(multiplier)

            # 2. Conversion Based Unit (e.g., inch, foot)
            elif unit.is_a("IfcConversionBasedUnit"):
                unit_type = getattr(unit, "UnitType", "")
                if unit_type == "LENGTHUNIT":
                    name = getattr(unit, "Name", "CUSTOM_LENGTH")
                    conversion_factor = getattr(unit, "ConversionFactor", None)
                    if conversion_factor and hasattr(conversion_factor, "ValueComponent"):
                        scale = float(conversion_factor.ValueComponent.wrappedValue)
                        return name, scale

    # Default fallback per ISO 10303-21 / IFC standard is meters
    return "METRE", 1.0
