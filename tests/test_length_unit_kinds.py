"""Only length units that resolve to metres through SI are accepted."""

from pathlib import Path

import ifcopenshell
import pytest

from ifc_to_fds.core.units import get_length_unit_scale

TINY = Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc"


def _with_length_unit(make_unit):
    f = ifcopenshell.open(str(TINY))
    old = next(u for u in f.by_type("IfcSIUnit") if u.UnitType == "LENGTHUNIT")
    new = make_unit(f, old)
    assignment = f.by_type("IfcUnitAssignment")[0]
    assignment.Units = tuple(new if u == old else u for u in assignment.Units)
    return f


def _length_dimensions(f):
    return f.create_entity("IfcDimensionalExponents", 1, 0, 0, 0, 0, 0, 0)


def test_si_metre_and_millimetre():
    assert get_length_unit_scale(ifcopenshell.open(str(TINY))) == ("METRE", 1.0)
    f = _with_length_unit(lambda f, u: f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"))
    assert get_length_unit_scale(f) == ("MILLIMETRE", pytest.approx(0.001))


def test_conversion_based_foot_goes_through_si():
    def foot(f, si):
        factor = f.create_entity(
            "IfcMeasureWithUnit", ValueComponent=f.create_entity("IfcLengthMeasure", 0.3048), UnitComponent=si
        )
        return f.create_entity(
            "IfcConversionBasedUnit", Dimensions=_length_dimensions(f), UnitType="LENGTHUNIT", Name="FOOT", ConversionFactor=factor
        )

    name, scale = get_length_unit_scale(_with_length_unit(foot))
    assert (name, scale) == ("FOOT", pytest.approx(0.3048))


def test_context_dependent_unit_is_rejected():
    f = _with_length_unit(
        lambda f, u: f.create_entity(
            "IfcContextDependentUnit", Dimensions=_length_dimensions(f), UnitType="LENGTHUNIT", Name="CUSTOM_LENGTH"
        )
    )
    with pytest.raises(ValueError, match="cannot be converted to metres"):
        get_length_unit_scale(f)


def test_conversion_unit_that_does_not_end_in_si_length_is_rejected():
    def bad(f, si):
        context_unit = f.create_entity(
            "IfcContextDependentUnit", Dimensions=_length_dimensions(f), UnitType="LENGTHUNIT", Name="X"
        )
        factor = f.create_entity(
            "IfcMeasureWithUnit", ValueComponent=f.create_entity("IfcLengthMeasure", 2.0), UnitComponent=context_unit
        )
        return f.create_entity(
            "IfcConversionBasedUnit", Dimensions=_length_dimensions(f), UnitType="LENGTHUNIT", Name="BAD", ConversionFactor=factor
        )

    with pytest.raises(ValueError, match="cannot be converted to metres"):
        get_length_unit_scale(_with_length_unit(bad))


def test_cli_rejects_custom_length_unit_with_exit_3(tmp_path, capsys):
    from ifc_to_fds import cli

    f = _with_length_unit(
        lambda f, u: f.create_entity(
            "IfcContextDependentUnit", Dimensions=_length_dimensions(f), UnitType="LENGTHUNIT", Name="CUSTOM_LENGTH"
        )
    )
    src = tmp_path / "custom.ifc"
    f.write(str(src))
    assert cli.main(["convert", str(src), "-o", str(tmp_path / "o.fds")]) == 3
    assert "cannot be converted to metres" in capsys.readouterr().err
