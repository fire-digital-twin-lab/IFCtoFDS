"""Kiểm thời điểm và định danh cửa đóng/mở trong đầu ra FDS."""

import os
import re

import pytest

from ifc_to_fds.validation.acceptance import AuditConfig
from ifc_to_fds.validation.effective import effective_obstructions
from ifc_to_fds.validation.solver import solver_gates


DECK = (
    "&HEAD CHID='door_timeline' /\n"
    "&MESH ID='room', IJK=10,10,10, XB=0,1,0,1,0,1 /\n"
    "&TIME T_END=2, DT=0.05, LOCK_TIME_STEP=.TRUE. /\n"
    "&OBST ID='wall_below', XB=0.4,0.6,0,1,0,0.2 /\n"
    "&OBST ID='door_opening', XB=0.4,0.6,0.2,0.8,0.2,0.8, DEVC_ID='clock_open' /\n"
    "&OBST ID='door_closing', XB=0.7,0.8,0.2,0.8,0.2,0.8, CTRL_ID='clock_close_ctrl' /\n"
    "&DEVC ID='clock_open', QUANTITY='TIME', XYZ=0.1,0.1,0.1, SETPOINT=0.8, INITIAL_STATE=.TRUE. /\n"
    "&DEVC ID='clock_close', QUANTITY='TIME', XYZ=0.1,0.1,0.1, SETPOINT=1.2, INITIAL_STATE=.FALSE. /\n"
    "&CTRL ID='clock_close_ctrl', FUNCTION_TYPE='ANY', INPUT_ID='clock_close', INITIAL_STATE=.FALSE. /\n"
    "&TAIL /\n"
)

EVENTS = "HIDE_OBST     1\n     3      0.000000\nHIDE_OBST     1\n     2      0.850000\nSHOW_OBST     1\n     3      1.250000\n"


def _smv(events=EVENTS):
    grids = "".join(
        tag + "\n0\n" + "".join(f"{i} {i / 10:.5f}\n" for i in range(11))
        for tag in ("TRNX", "TRNY", "TRNZ")
    )
    return (
        "GRID room\n" + grids + "OBST\n3\n"
        "0.4 0.6 0 1 0 0.2 1 0 0 0 0 0 0 ! wall_below\n"
        "0.4 0.6 0.2 0.8 0.2 0.8 2 0 0 0 0 0 0 ! door_opening\n"
        "0.7 0.8 0.2 0.8 0.2 0.8 3 0 0 0 0 0 0 ! door_closing\n"
        "4 6 0 10 0 2 -1 -1 ! F\n4 6 2 8 2 8 -1 -1 ! T\n7 8 2 8 2 8 -1 -1 ! T\n"
        + events
    )


def test_door_events_are_tied_to_obstruction_row_and_expected_time():
    result = effective_obstructions(DECK, _smv())
    assert result.status == "PASS", result.reason
    opening = result.evidence["obstruction_timeline"]["door_opening"]
    closing = result.evidence["obstruction_timeline"]["door_closing"]
    assert opening["initial_present"] is True and opening["final_present"] is False
    assert closing["initial_present"] is False and closing["final_present"] is True
    assert opening["transition_s"] == pytest.approx(0.85)
    assert closing["transition_s"] == pytest.approx(1.25)

    assert effective_obstructions(DECK, _smv(EVENTS.replace("2      0.850000", "1      0.850000"))).status == "FAIL"
    assert effective_obstructions(DECK, _smv(EVENTS.replace("0.850000", "0.750000"))).status == "FAIL"
    assert effective_obstructions(DECK, _smv(EVENTS.replace("0.850000", "1.050000"))).status == "FAIL"
    assert effective_obstructions(DECK, _smv(EVENTS.replace("     3      0.000000\n", "     2      0.000000\n"))).status == "FAIL"
    reordered = "\n".join(EVENTS.splitlines()[2:] + EVENTS.splitlines()[:2]) + "\n"
    assert effective_obstructions(DECK, _smv(reordered)).status == "FAIL"
    assert effective_obstructions(DECK, _smv("HIDE_OBST 1\n")).status == "INCONCLUSIVE"
    assert effective_obstructions(DECK, _smv("")).status == "INCONCLUSIVE"
    assert effective_obstructions(DECK.replace("LOCK_TIME_STEP=.TRUE.", "LOCK_TIME_STEP=.FALSE."), _smv()).status == "INCONCLUSIVE"


@pytest.mark.solver
def test_pinned_fds_proves_two_opposite_door_transitions(tmp_path):
    solver, result = solver_gates(DECK, AuditConfig(
        solver_executable=os.environ["IFCFDS_SOLVER"], solver_evidence_directory=str(tmp_path),
    ))
    assert solver.status == "PASS", solver.reason
    assert result.status == "PASS", result.reason
    data = result.evidence["obstruction_timeline"]
    assert 0.8 <= data["door_opening"]["transition_s"] <= 0.900001
    assert 1.2 <= data["door_closing"]["transition_s"] <= 1.300001
    assert data["door_opening"]["final_present"] is False
    assert data["door_closing"]["final_present"] is True
    smv = next(tmp_path.glob("*/*.smv")).read_text()
    mutated, count = re.subn(r"(?m)^(SHOW_OBST\s+1\n +)3( +[0-9.]+)$", r"\g<1>2\2", smv)
    assert count == 1
    assert effective_obstructions(DECK, mutated).status == "FAIL"
