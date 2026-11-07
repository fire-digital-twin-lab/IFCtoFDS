from __future__ import annotations

import pytest

from ifc_to_fds.validation.parser import parse_fds


def _contract_text() -> str:
    return """&HEAD CHID='parser_contract', TITLE='FDS 6.11.1 parser contract' /
&MESH ID='M1', IJK=4,4,4, XB=0,1,0,1,0,1 /
&TIME T_END=0.1 /
&MATL ID='STEEL', DENSITY=7850, CONDUCTIVITY=54, SPECIFIC_HEAT=0.465, EMISSIVITY=0.9 /
&SURF ID='STEEL_SURF', MATL_ID(1,:)='STEEL', THICKNESS=0.01 /
&SPEC ID='WATER VAPOR' /
&PART ID='WATER', SPEC_ID='WATER VAPOR', DIAMETER=500, SAMPLING_FACTOR=5, QUANTITIES(1:2)='PARTICLE DIAMETER','PARTICLE AGE' /
&PROP ID='SPRINKLER', QUANTITY='SPRINKLER LINK TEMPERATURE', RTI=50, C_FACTOR=0.7, ACTIVATION_TEMPERATURE=74, OFFSET=0.05, PART_ID='WATER', FLOW_RATE=5, PARTICLE_VELOCITY=5, SPRAY_ANGLE=50,55 /
&REAC ID='PROPANE_REAC', FUEL='PROPANE', CO_YIELD=0.01, SOOT_YIELD=0.01, RADIATIVE_FRACTION=0.35 /
&OBST ID='BOX', XB=0.2,0.8,0.2,0.8,0.2,0.8, SURF_ID='STEEL_SURF' /
&DEVC ID='SPR-1', XYZ=0.5,0.5,0.9, PROP_ID='SPRINKLER', ORIENTATION=0,0,-1 /
&DEVC ID='HF-1', XB=0.2,0.8,0.5,0.5,0.4,0.4, QUANTITY='GAUGE HEAT FLUX', IOR=2, TIME_AVERAGED=.FALSE. /
&SLCF ID='TEMP_Z', PBZ=0.5, QUANTITY='TEMPERATURE', VECTOR=.TRUE., CELL_CENTERED=.TRUE. /
&SLCF ID='DROP_Z', PBZ=0.5, QUANTITY='MPUV', PART_ID='WATER' /
&BNDF QUANTITY='WALL TEMPERATURE', CELL_CENTERED=.TRUE., MATL_ID='STEEL' /
&ISOF QUANTITY='TEMPERATURE', VALUE=50 /
&HVAC ID='FAN-1', TYPE_ID='FAN', MAX_FLOW=2.0, MAX_PRESSURE=500, TAU_FAN=1.0 /
&TAIL /
"""


def test_scientific_namelist_contract_accepts_supported_fds_subset() -> None:
    parsed = parse_fds(_contract_text())
    assert parsed.errors == []
    assert parsed.unsupported == []
    kinds = {record.kind for record in parsed.records}
    assert {"MATL", "PART", "PROP", "SLCF", "BNDF", "ISOF"} <= kinds
    surface = next(record for record in parsed.records if record.kind == "SURF")
    assert surface.values["MATL_ID(1,:)"] == ["STEEL"]


@pytest.mark.parametrize(
    ("old", "new", "expected_error"),
    [
        (
            "PROP_ID='SPRINKLER'",
            "PROP_ID='MISSING_PROP'",
            "DEVC SPR-1: PROP_ID references missing PROP MISSING_PROP",
        ),
        (
            "PART_ID='WATER', FLOW_RATE=5",
            "PART_ID='MISSING_PART', FLOW_RATE=5",
            "PROP SPRINKLER: PART_ID references missing PART MISSING_PART",
        ),
        (
            "MATL_ID(1,:)='STEEL'",
            "MATL_ID(1,:)='MISSING_MATL'",
            "SURF STEEL_SURF: MATL_ID references missing MATL MISSING_MATL",
        ),
    ],
)
def test_scientific_reference_integrity_rejects_dangling_ids(
    old: str, new: str, expected_error: str
) -> None:
    parsed = parse_fds(_contract_text().replace(old, new))
    assert expected_error in parsed.errors


@pytest.mark.parametrize(
    ("old", "new", "expected_error"),
    [
        ("&MATL ID='STEEL',", "&MATL", "MATL requires ID"),
        (
            "&ISOF QUANTITY='TEMPERATURE', VALUE=50 /",
            "&ISOF VALUE=50 /",
            "ISOF requires QUANTITY",
        ),
        (
            "RTI=50",
            "RTI=nan",
            "Non-finite numeric value",
        ),
    ],
)
def test_scientific_contract_rejects_missing_or_nonfinite_data(
    old: str, new: str, expected_error: str
) -> None:
    parsed = parse_fds(_contract_text().replace(old, new))
    assert any(expected_error in error for error in parsed.errors)


def test_scientific_contract_keeps_unknown_field_fail_closed() -> None:
    parsed = parse_fds(
        _contract_text().replace(
            "&MATL ID='STEEL',",
            "&MATL ID='STEEL', UNSUPPORTED_SCIENCE_FIELD=1,",
        )
    )
    assert "MATL.UNSUPPORTED_SCIENCE_FIELD" in parsed.unsupported


def test_reference_integrity_is_namelist_order_invariant() -> None:
    text = _contract_text()
    prop = "&PROP ID='SPRINKLER', QUANTITY='SPRINKLER LINK TEMPERATURE', RTI=50, C_FACTOR=0.7, ACTIVATION_TEMPERATURE=74, OFFSET=0.05, PART_ID='WATER', FLOW_RATE=5, PARTICLE_VELOCITY=5, SPRAY_ANGLE=50,55 /\n"
    assert prop in text
    moved = text.replace(prop, "").replace("&TAIL /", prop + "&TAIL /")
    parsed = parse_fds(moved)
    assert parsed.errors == []
    assert parsed.unsupported == []


def test_indexed_field_tokenizer_rejects_unbalanced_parentheses() -> None:
    parsed = parse_fds(
        _contract_text().replace(
            "MATL_ID(1,:)='STEEL'",
            "MATL_ID(1,:='STEEL'",
        )
    )
    assert "Unbalanced field index parentheses" in parsed.errors
