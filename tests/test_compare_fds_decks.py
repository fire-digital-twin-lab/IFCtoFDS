"""scripts/compare-fds-decks.py measures two decks without IFC provenance (PyroSim cross-check)."""

import runpy
from pathlib import Path

import pytest

compare = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "compare-fds-decks.py"))["compare"]

HEAD = "&HEAD CHID='t' /\n&MESH IJK=40,20,30, XB=0,4,0,2,0,3 /\n&TIME T_END=0 /\n"


def deck(*lines):
    return HEAD + "\n".join(lines) + "\n&TAIL /\n"


def test_a_wall_with_a_hole_equals_the_same_wall_built_from_pieces():
    # IFCtoFDS writes box sets; a PyroSim user may cut a door with HOLE. Same space, different records.
    holed = deck("! IFC_SOURCE {\"entity_key\": \"s:1\"}", "&OBST ID='W', XB=0,4,0,0.2,0,3 /", "&HOLE ID='D', XB=1,2,-0.1,0.3,0,2 /")
    pieces = deck("&OBST ID='A', XB=0,1,0,0.2,0,3 /", "&OBST ID='B', XB=2,4,0,0.2,0,3 /", "&OBST ID='C', XB=1,2,0,0.2,2,3 /")
    result = compare(holed, pieces)
    expected = 4 * 0.2 * 3 - 1 * 0.2 * 2
    assert result["a"]["solid_volume_m3"] == pytest.approx(expected, abs=1e-9)
    assert result["b"]["solid_volume_m3"] == pytest.approx(expected, abs=1e-9)
    assert result["comparison"]["iou"] == pytest.approx(1.0, abs=1e-6)
    assert result["a"]["provenance_lines"] == 1 and result["b"]["provenance_lines"] == 0


def test_a_missing_obstruction_is_measured_and_located():
    a = deck("&OBST ID='W', XB=0,4,0,0.2,0,3 /", "&OBST ID='COL', XB=3,3.5,1,1.5,0,3 /")
    b = deck("&OBST ID='W', XB=0,4,0,0.2,0,3 /")
    cmp = compare(a, b)["comparison"]
    assert cmp["only_a_m3"] == pytest.approx(0.75, abs=1e-9)
    assert cmp["only_b_m3"] == pytest.approx(0.0, abs=1e-9)
    assert cmp["only_a_regions"][0]["bounds"] == [3.0, 1.0, 0.0, 3.5, 1.5, 3.0]


def test_identical_decks_take_the_exact_path():
    text = deck("&OBST ID='W', XB=0,4,0,0.2,0,3 /", "&OBST ID='X', XB=0,0.2,0,2,0,3 /")
    cmp = compare(text, text)["comparison"]
    assert cmp["method"] == "IDENTICAL_SPACE" and cmp["only_a_m3"] == 0.0


def test_hvac_node_losses_and_unmodelled_records_are_reported():
    hvac = (
        "&HVAC TYPE_ID='DUCT', ID='D1', NODE_ID='N1','N2', AREA=0.1, LENGTH=1 /",
        "&HVAC TYPE_ID='DUCT', ID='D2', NODE_ID='N2','N3', AREA=0.1, LENGTH=1 /",
        "&HVAC TYPE_ID='NODE', ID='N2', DUCT_ID='D1','D2', XYZ=1,1,1, LOSS(1,2)=0.5, LOSS(2,1)=0.7 /",
    )
    full = deck("&OBST ID='W', XB=0,4,0,0.2,0,3 /", *hvac)
    lost = deck("&OBST ID='W', XB=0,4,0,0.2,0,3, MULT_ID='M' /", *hvac[:2])
    result = compare(full, lost)
    assert result["a"]["node_loss_pairs"] == 2 and result["b"]["node_loss_pairs"] == 0
    assert result["a"]["hvac"] == {"DUCT": 2, "NODE": 1} and result["b"]["hvac"] == {"DUCT": 2}
    assert result["b"]["flagged"] == {"OBST with MULT_ID": 1}


def test_a_record_the_parser_refuses_is_reported_not_dropped():
    # FDS accepts a zero-thickness OBST; the strict parser does not, so it is listed instead of measured.
    result = compare(deck("&OBST ID='P', XB=0,4,1,1,0,3 /", "&OBST ID='W', XB=0,4,0,0.2,0,3 /"),
                     deck("&OBST ID='W', XB=0,4,0,0.2,0,3 /"))
    assert result["a"]["parse_errors"] == 1
    assert "positive extents" in result["a"]["parse_error_samples"][0]
