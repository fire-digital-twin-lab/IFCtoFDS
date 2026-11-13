"""Đối chiếu lỗ xuyên tường tại đường nối hai mesh FDS."""

import os
import re

import pytest

from ifc_to_fds.validation.acceptance import AuditConfig
from ifc_to_fds.validation.effective import effective_obstructions
from ifc_to_fds.validation.solver import solver_gates


def _deck(split):
    if split == "normal":
        near = "IJK=5,10,10, XB=0,0.5,0,1,0,1"
        far = "IJK=5,10,10, XB=0.5,1,0,1,0,1"
    else:
        near = "IJK=10,5,10, XB=0,1,0,0.5,0,1"
        far = "IJK=10,5,10, XB=0,1,0.5,1,0,1"
    return (
        "&HEAD CHID='hole_multimesh' /\n&TIME T_END=0 /\n"
        f"&MESH ID='near', {near} /\n&MESH ID='far', {far} /\n"
        "&OBST ID='wall', XB=0.4,0.6,0,1,0,1 /\n"
        "&HOLE ID='opening', XB=0.3,0.7,0.2,0.8,0.2,0.6 /\n&TAIL /\n"
    )


def _smv_section(mesh_id, *, offset, pieces):
    grids = "".join(
        tag + "\n0\n" + "".join(f"{i} {start + i / 10:.5f}\n" for i in range(count + 1))
        for tag, start, count in (("TRNX", offset, 5), ("TRNY", 0, 10), ("TRNZ", 0, 10))
    )
    return (
        f"GRID {mesh_id}\n" + grids + f"OBST\n{len(pieces)}\n"
        + "0 0 0 0 0 0 ! wall\n" * len(pieces)
        + "".join(f"{row} -1 -1 ! F\n" for row in pieces)
    )


def test_multimesh_hole_detects_one_covered_interface_face():
    sections = [
        _smv_section(mesh_id, offset=offset, pieces=[
            f"{first} {last} 2 8 6 10", f"{first} {last} 0 2 0 10",
            f"{first} {last} 8 10 0 10", f"{first} {last} 2 8 0 2",
        ])
        for mesh_id, offset, first, last in (("near", 0, 4, 5), ("far", 0.5, 0, 1))
    ]
    deck = _deck("normal")
    smv = "".join(sections)
    result = effective_obstructions(deck, smv)
    assert result.status == "PASS", result.reason
    data = result.evidence["static_hole"]
    assert data["effective_wall_cells"] == 152
    assert data["open_area_m2"] == pytest.approx(0.24)
    assert data["interface"]["open_area_m2"] == pytest.approx(0.24)
    wrong = sections[0] + sections[1].replace("0 1 2 8 0 2", "0 1 2 8 0 3")
    assert effective_obstructions(deck, wrong).status == "FAIL"
    thin = sections[0] + sections[1].replace("0 1 2 8 0 2", "0 0 2 8 2 6")
    assert effective_obstructions(deck, thin).status == "INCONCLUSIVE"
    gap = deck.replace("XB=0.5,1,0,1,0,1", "XB=0.6,1,0,1,0,1")
    assert effective_obstructions(gap, smv).status == "INCONCLUSIVE"
    unequal = deck.replace("IJK=5,10,10, XB=0.5", "IJK=5,20,10, XB=0.5")
    assert effective_obstructions(unequal, smv).status == "INCONCLUSIVE"


@pytest.mark.solver
@pytest.mark.parametrize("split", ["normal", "tangent"])
def test_pinned_fds_static_hole_crosses_a_matching_mesh_interface(split, tmp_path):
    deck = _deck(split)
    solver, effective = solver_gates(deck, AuditConfig(
        solver_executable=os.environ["IFCFDS_SOLVER"], solver_evidence_directory=str(tmp_path),
    ))
    assert solver.status == "PASS", solver.reason
    assert effective.status == "PASS", effective.reason
    hole = effective.evidence["static_hole"]
    assert hole["effective_wall_cells"] == 152
    assert hole["open_area_m2"] == pytest.approx(0.24)
    assert hole["interface"]["open_area_m2"] == pytest.approx(0.24 if split == "normal" else 0.08)
    assert set(hole["mesh_obstructions"]) == {"near", "far"}
    smv = next(tmp_path.glob("*/*.smv")).read_text()
    far = smv.index("GRID   far")
    mutated, count = re.subn(r"(?m)^( +\d+ +\d+ +\d+ +\d+ +)6( +10 +-?\d+ +-?\d+ ! F)", r"\g<1>5\2", smv[far:], count=1)
    assert count == 1
    assert effective_obstructions(deck, smv[:far] + mutated).status == "FAIL"
