import os
import re
import pytest

from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation.effective import effective_obstructions


STATIC_HOLE = (
    "&HEAD CHID='effective_hole' /\n&TIME T_END=0 /\n"
    "&MESH ID='room', IJK=10,10,10, XB=0,1,0,1,0,1 /\n"
    "&OBST ID='wall', XB=0.4,0.6,0,1,0,1 /\n"
    "&HOLE ID='window', XB=0.3,0.7,0.3,0.7,0.2,0.6 /\n"
    "&TAIL /\n"
)


def test_effective_static_hole_is_proved_from_all_solver_pieces():
    # Reference integer occupancy of a 2×10×10 cell wall minus a 2×4×4
    # passage. The SMV's first table may contain unsnapped coordinates.
    rows = [
        "4 6 3 7 6 10",
        "4 6 0 3 0 10",
        "4 6 7 10 0 10",
        "4 6 3 7 0 2",
    ]
    grids = "".join(
        tag + "\n0\n" + "".join(f"{i} {i / 10:.5f}\n" for i in range(11)) + "\n"
        for tag in ("TRNX", "TRNY", "TRNZ")
    )
    smv = grids + "OBST\n4\n" + "0 0 0 0 0 0 ! wall\n" * 4
    smv += "".join(row + " 0 0 ! F\n" for row in rows)
    effective = effective_obstructions(STATIC_HOLE, smv)
    assert effective.status == "PASS", effective.reason
    hole = effective.evidence["static_hole"]
    assert hole["effective_wall_cells"] == 168
    assert hole["open_area_m2"] == pytest.approx(0.16)
    assert hole["through_axis"] == "X"
    assert effective_obstructions(
        STATIC_HOLE, smv.replace(rows[1], "4 6 0 4 0 10")
    ).status == "FAIL"
    assert effective_obstructions(
        STATIC_HOLE, smv.replace(rows[3], "4 6 3 7 0 1")
    ).status == "FAIL"
    assert effective_obstructions(
        STATIC_HOLE.replace("0.3,0.7,0.2,0.6", "0.34,0.7,0.2,0.6"), smv
    ).status == "INCONCLUSIVE"
    assert effective_obstructions(
        STATIC_HOLE.replace("ID='window',", "ID='window', DEVC_ID='timer',"), smv
    ).status == "INCONCLUSIVE"
    assert effective_obstructions(STATIC_HOLE, smv, solver_version="6.10.1").status == "INCONCLUSIVE"


@pytest.mark.solver
def test_pinned_fds_static_hole_matches_analytic_occupancy(tmp_path):
    from ifc_to_fds.validation.acceptance import AuditConfig
    from ifc_to_fds.validation.solver import solver_gates

    solver, effective = solver_gates(STATIC_HOLE, AuditConfig(
        solver_executable=os.environ["IFCFDS_SOLVER"],
        solver_evidence_directory=str(tmp_path),
    ))
    assert solver.status == "PASS", solver.reason
    assert effective.status == "PASS", effective.reason
    hole = effective.evidence["static_hole"]
    assert hole["effective_wall_cells"] == 168
    assert hole["open_area_m2"] == pytest.approx(0.16)
    smv = next(tmp_path.glob("*/*.smv")).read_text()
    mutated, count = re.subn(r"(?m)^ +4 +6 +0 +3 +0 +10(?= )", " 4 6 0 4 0 10", smv)
    assert count == 1
    assert effective_obstructions(STATIC_HOLE, mutated).status == "FAIL"


def smv_for_box(pid, indices):
    # Format taken from FDS 6.11.1 Source/dump.f90, not an asserted solver run.
    text = ""
    for axis in ("TRNX", "TRNY", "TRNZ"):
        text += (
            axis + "\n0\n" + "".join(f"{i} {i * 0.2:.5f}\n" for i in range(21)) + "\n"
        )
    return (
        text
        + "OBST\n1\n0 2 0 1 0 3 1 1 1 1 1 1 1 ! "
        + pid
        + "\n"
        + " ".join(map(str, indices))
        + " 0 0 ! F\n"
    )


def test_solver_integer_indices_drive_effective_bounds(box_model):
    text, _ = serialize_fds(box_model)
    # Set a known 4x4x4 / 0.2m mesh for this parser fixture.
    text = re.sub(r"&MESH[^/]+/", "&MESH IJK=20,20,20, XB=0,4,0,4,0,4 /", text)
    pid = box_model.elements[0].fds_primitive_ids[0]
    result = effective_obstructions(text, smv_for_box(pid, [0, 10, 0, 5, 0, 15]))
    assert result.status == "PASS"
    assert result.evidence["effective_bounds"][pid] == [0.0, 2.0, 0.0, 1.0, 0.0, 3.0]
    collapsed = effective_obstructions(text, smv_for_box(pid, [0, 0, 0, 5, 0, 15]))
    assert collapsed.status == "FAIL" and "collapsed" in collapsed.reason


def test_unknown_effective_output_is_inconclusive(box_model):
    text, _ = serialize_fds(box_model)
    assert effective_obstructions(text, "not a smokeview file").status == "INCONCLUSIVE"
    from ifc_to_fds.mapping.policy import plan_mapping

    plan_mapping(box_model, force_all_geom=True)
    text, _ = serialize_fds(box_model)
    assert effective_obstructions(text, "").status == "INCONCLUSIVE"


def test_unsupported_effective_syntax_and_bad_indices_never_pass(box_model):
    text, _ = serialize_fds(box_model)
    text = re.sub(r"&MESH[^/]+/", "&MESH IJK=20,20,20, XB=0,4,0,4,0,4 /", text)
    pid = box_model.elements[0].fds_primitive_ids[0]
    smv = smv_for_box(pid, [0, 10, 0, 5, 0, 15])
    for extra in (
        "&HOLE ID='h', XB=0,1,0,1,0,1 /",
        "&VENT ID='v', XB=0,0,0,1,0,1 /",
        "&MESH IJK=20,20,20, XB=4,8,0,4,0,4 /",
    ):
        assert effective_obstructions(text + extra, smv).status == "INCONCLUSIVE"
    invalid = effective_obstructions(text, smv_for_box(pid, [-1, 10, 0, 5, 0, 15]))
    assert invalid.status == "INCONCLUSIVE"
    assert "outside" in invalid.reason
    tie = text.replace("XB=0,2,0,1,0,3", "XB=0.1,2,0,1,0,3")
    assert tie != text
    assert effective_obstructions(tie, smv).status == "INCONCLUSIVE"


@pytest.mark.solver
def test_fds_effective_obstruction_crossing_mesh_boundary(tmp_path):
    from ifc_to_fds.validation.acceptance import AuditConfig
    from ifc_to_fds.validation.solver import solver_gates

    text = (
        "&HEAD CHID='multieff' /\n&TIME T_END=0 /\n"
        "&MESH ID='west', IJK=10,10,10, XB=0,1,0,1,0,1 /\n"
        "&MESH ID='east', IJK=10,10,10, XB=1,2,0,1,0,1 /\n"
        "&OBST ID='cross', XB=0.6,1.4,0.2,0.5,0.2,0.8 /\n"
        "&OBST ID='east_only', XB=1.6,1.8,0.2,0.5,0.2,0.8 /\n&TAIL /\n"
    )
    solver, effective = solver_gates(text, AuditConfig(
        solver_executable=os.environ["IFCFDS_SOLVER"],
        solver_evidence_directory=str(tmp_path),
    ))
    assert solver.status == "PASS", solver.reason
    assert effective.status == "PASS", effective.reason
    pieces = effective.evidence["mesh_obstructions"]
    assert pieces["west"]["cross"] == [.6, 1, .2, .5, .2, .8]
    assert pieces["east"]["cross"] == [1, 1.4, .2, .5, .2, .8]
    assert effective.evidence["effective_bounds"]["cross"] == [.6, 1.4, .2, .5, .2, .8]
    smv = next(tmp_path.glob("*/*.smv")).read_text()
    altered = smv.replace("! cross", "! other", 1)
    assert effective_obstructions(text, altered).status == "FAIL"
