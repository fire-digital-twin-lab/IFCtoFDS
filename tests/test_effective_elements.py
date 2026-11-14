"""The effective-geometry gate reports what it cannot read per element and never hides a verified failure.

The SMV files in tests/data/effective were written by the pinned FDS 6.11.1 (set-up only) from the .fds beside them.
"""

import os
import re
from pathlib import Path

import pytest

from ifc_to_fds.validation.effective import effective_obstructions

DATA = Path(__file__).parent / "data" / "effective"
GEOM = "&GEOM ID='g', VERTS=0,0,0, 1,0,0, 0,1,0, 0,0,1, FACES=1,2,3,1, 1,2,4,1, 2,3,4,1, 1,3,4,1 /\n"


def load(name):
    return (DATA / f"{name}.fds").read_text(), (DATA / f"{name}.smv").read_text()


def test_vents_and_controlled_obstruction_are_verified_from_the_smv():
    result = effective_obstructions(*load("vents_ok"))
    assert result.status == "PASS", result.reason
    elements = result.evidence["elements"]
    assert {k: v["status"] for k, v in elements.items()} == {"V_TOP": "PASS", "V_OPEN": "PASS"}
    assert result.evidence["dynamic_obstructions"] == ["O2"]
    assert set(result.evidence["effective_bounds"]) == {"O1", "O2"}


def test_a_vent_the_solver_dropped_fails_by_name():
    result = effective_obstructions(*load("vent_thin"))
    assert result.status == "FAIL" and "V_THIN" in result.reason


def test_geom_is_inconclusive_for_itself_only():
    fds, smv = load("vents_ok")
    result = effective_obstructions(fds.replace("&TAIL /", GEOM + "&TAIL /"), smv)
    assert result.status == "INCONCLUSIVE"
    assert result.evidence["elements"]["g"]["status"] == "INCONCLUSIVE"
    assert result.evidence["elements"]["V_TOP"]["status"] == "PASS"
    assert "2 OBST/VENT verified" in result.reason or "4 OBST/VENT verified" in result.reason


def test_geom_does_not_hide_a_collapsed_obstruction():
    fds, smv = load("vents_ok")
    collapsed = re.sub(r"^\s+3\s+5\s+3\s+7\s+0\s+5\s", "    3    3    3    7    0    5 ", smv, flags=re.M)
    assert collapsed != smv
    result = effective_obstructions(fds.replace("&TAIL /", GEOM + "&TAIL /"), collapsed)
    assert result.status == "FAIL" and "collapsed" in result.reason


def test_vent_without_a_vent_table_is_inconclusive():
    fds, smv = load("vents_ok")
    lines = smv.splitlines()
    cut = lines.index("VENT")
    result = effective_obstructions(fds, "\n".join(lines[:cut]))
    assert result.status == "INCONCLUSIVE"
    assert result.evidence["elements"]["V_TOP"]["status"] == "INCONCLUSIVE"


@pytest.mark.solver
def test_real_solver_output_for_vents_across_a_mesh_seam(tmp_path):
    from ifc_to_fds.validation.acceptance import AuditConfig
    from ifc_to_fds.validation.solver import solver_gates

    text = "\n".join([
        "&HEAD CHID='seam' /", "&TIME T_END=0 /", "&SURF ID='S', COLOR='RED' /",
        "&MESH ID='west', IJK=10,10,10, XB=0,1,0,1,0,1 /",
        "&MESH ID='east', IJK=10,10,10, XB=1,2,0,1,0,1 /",
        "&VENT ID='V_SEAM', XB=0.42,1.58,0.22,0.78,0,0, SURF_ID='S' /", "&TAIL /", "",
    ])
    solver, effective = solver_gates(
        text, AuditConfig(solver_executable=os.environ["IFCFDS_SOLVER"], solver_evidence_directory=str(tmp_path))
    )
    assert solver.status == "PASS", solver.reason
    assert effective.evidence["elements"]["V_SEAM"]["status"] == "PASS", effective.evidence.get("elements")


def test_grid_that_is_not_a_round_multiple_is_read_within_the_smv_print_precision():
    """Real models give cells like 0.19952 m; the SMV prints five decimals, so the grid is off by up to 5e-6."""
    import numpy as np

    fds, smv = load("odd_grid")
    lines = smv.splitlines()
    first = lines.index("TRNX")
    planes = [float(row.split()[1]) for row in lines[first + 2 : first + 2 + 12]]
    ideal = np.linspace(0.123456, 2.345678, 12)
    assert 1e-7 < np.abs(np.array(planes) - ideal).max() < 1e-5  # why the old 1e-7 tolerance rejected it
    result = effective_obstructions(fds, smv)
    assert result.status == "PASS", result.reason
    assert result.evidence["elements"]["V_TOP"]["status"] == "PASS"
