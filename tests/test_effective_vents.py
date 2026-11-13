"""Đối chiếu ô thoáng ngoài miền bằng chỉ số mặt do FDS ghi."""

import os
import re

import pytest

from ifc_to_fds.validation.acceptance import AuditConfig
from ifc_to_fds.validation.effective import effective_obstructions
from ifc_to_fds.validation.solver import solver_gates


DECK = (
    "&HEAD CHID='effective_vents' /\n&TIME T_END=0 /\n"
    "&MESH ID='room', IJK=10,10,10, XB=0,1,0,1,0,1 /\n"
    "&VENT ID='window', XB=0,0,0.2,0.6,0.3,0.8, SURF_ID='OPEN' /\n"
    "&TAIL /\n"
)


def _smv(*, face="0 0 2 6 3 8 -99 2 ! 1", with_face=True):
    grids = "".join(
        tag + "\n0\n" + "".join(f"{i} {i / 10:.5f}\n" for i in range(11))
        for tag in ("TRNX", "TRNY", "TRNZ")
    )
    return (
        "VENTORIG\n1\n0 0 0.2 0.6 0.3 0.8 ! window\nGRID room\n"
        + grids + "OBST\n0\n"
        + ("VENT\n2 1\n0 0 0.2 0.6 0.3 0.8 1 1\n"
           "1 1 0 1 0 1 2 0\n" + face + "\n10 10 0 10 0 10 99 0\n"
           if with_face else "VENT\n1 1\n1 1 0 1 0 1 1 0\n10 10 0 10 0 10 99 0\n")
        + "CVENT\n0\n"
    )


def test_open_vent_requires_effective_face_indices_and_orientation():
    result = effective_obstructions(DECK, _smv())
    assert result.status == "PASS", result.reason
    assert result.evidence["open_vents"]["window"]["area_m2"] == pytest.approx(0.2)
    assert result.evidence["open_vents"]["window"]["face_cells"] == 20
    assert effective_obstructions(DECK, _smv(face="0 0 2 5 3 8 -99 2 ! 1")).status == "FAIL"
    assert effective_obstructions(DECK, _smv(face="0 0 2 6 3 8 -99 2 ! -1")).status == "FAIL"
    assert effective_obstructions(DECK, _smv(face="0 0 2 6 3 8 99 0 ! 1")).status == "FAIL"
    assert effective_obstructions(DECK, _smv(with_face=False)).status == "FAIL"
    assert effective_obstructions(DECK, _smv().replace("! window", "! other")).status == "FAIL"
    assert effective_obstructions(DECK, _smv().replace("VENT\n2 1", "VENT\n3 1")).status == "INCONCLUSIVE"


@pytest.mark.solver
@pytest.mark.parametrize("case", ["clear", "snapped-high-face", "partly-blocked", "collapsed"])
def test_pinned_fds_exterior_open_vent_reports_effective_area(case, tmp_path):
    deck = DECK
    if case == "partly-blocked":
        deck = deck.replace("&TAIL", "&OBST ID='block', XB=0,0.2,0.3,0.5,0.4,0.6 /\n&TAIL")
    elif case == "snapped-high-face":
        deck = deck.replace("0,0,0.2,0.6,0.3,0.8", "1,1,0.23,0.58,0.32,0.79")
    elif case == "collapsed":
        deck = deck.replace("0.2,0.6,0.3,0.8", "0.22,0.23,0.32,0.33")
    solver, effective = solver_gates(deck, AuditConfig(
        solver_executable=os.environ["IFCFDS_SOLVER"], solver_evidence_directory=str(tmp_path),
    ))
    assert solver.status == "PASS", solver.reason
    assert effective.status == ("PASS" if case in ("clear", "snapped-high-face") else "FAIL"), effective.reason
    if case == "clear":
        vent = effective.evidence["open_vents"]["window"]
        assert vent["area_m2"] == pytest.approx(0.2)
        assert vent["face_cells"] == 20
        smv = next(tmp_path.glob("*/*.smv")).read_text()
        mutated, count = re.subn(r"(?m)^ +0 +0 +2 +6 +3 +8 +(-99 +2)", r" 0 0 2 5 3 8 \1", smv)
        assert count == 1
        assert effective_obstructions(deck, mutated).status == "FAIL"
    elif case == "snapped-high-face":
        vent = effective.evidence["open_vents"]["window"]
        assert vent["orientation"] == -1
        assert vent["area_m2"] == pytest.approx(0.2)
        assert vent["deck_area_m2"] == pytest.approx(0.1645)
    elif case == "partly-blocked":
        vent = effective.evidence["open_vents"]["window"]
        assert vent["blocked_face_cells"] == 4
        assert vent["open_area_m2"] == pytest.approx(0.16)
    else:
        assert "collapsed" in effective.reason.lower()
