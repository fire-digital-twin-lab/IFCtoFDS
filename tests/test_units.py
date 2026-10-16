import os
import ifcopenshell
from ifc_to_fds.core.units import get_length_unit_scale

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_unit_scale_extraction():
    # AC20-FZK-Haus.ifc uses METRE
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    ifc_file = ifcopenshell.open(fzk_path)
    unit_name, scale = get_length_unit_scale(ifc_file)
    assert unit_name == "METRE"
    assert scale == 1.0


def test_unit_scale_millimeter():
    # Duplex model uses millimetres (0.001 scale)
    duplex_path = os.path.join(REPO_ROOT, "examples", "IfcOpenShell-Duplex.ifc")
    ifc_file = ifcopenshell.open(duplex_path)
    unit_name, scale = get_length_unit_scale(ifc_file)
    assert unit_name == "METRE"
    assert scale == 1.0


def test_recursive_conversion_unit(tiny_ifc):
    import pytest

    path, file, _ = tiny_ifc
    metre = file.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    foot_factor = file.create_entity(
        "IfcMeasureWithUnit",
        ValueComponent=file.create_entity("IfcLengthMeasure", 0.3048),
        UnitComponent=metre,
    )
    dims = file.create_entity(
        "IfcDimensionalExponents",
        LengthExponent=1,
        MassExponent=0,
        TimeExponent=0,
        ElectricCurrentExponent=0,
        ThermodynamicTemperatureExponent=0,
        AmountOfSubstanceExponent=0,
        LuminousIntensityExponent=0,
    )
    foot = file.create_entity(
        "IfcConversionBasedUnit",
        Dimensions=dims,
        UnitType="LENGTHUNIT",
        Name="FOOT",
        ConversionFactor=foot_factor,
    )
    inch_factor = file.create_entity(
        "IfcMeasureWithUnit",
        ValueComponent=file.create_entity("IfcLengthMeasure", 1 / 12),
        UnitComponent=foot,
    )
    inch = file.create_entity(
        "IfcConversionBasedUnit",
        Dimensions=dims,
        UnitType="LENGTHUNIT",
        Name="INCH",
        ConversionFactor=inch_factor,
    )
    file.by_type("IfcProject")[0].UnitsInContext.Units = [inch]
    assert get_length_unit_scale(file)[1] == pytest.approx(0.0254)


def test_mm_geometry_scaled_once(tiny_ifc):
    import pytest
    from ifc_to_fds.core.federation import load_sources

    path, file, _ = tiny_ifc
    file.by_type("IfcProject")[0].UnitsInContext.Units[0].Prefix = "MILLI"
    file.write(str(path))
    model = load_sources([path])
    wall = next(e for e in model.elements if e.ifc_type == "IfcWall")
    assert wall.bounding_box.dx == pytest.approx(0.002)
    assert wall.bounding_box.dz == pytest.approx(0.003)
