from ifc_to_fds.validation.effective import effective_obstructions
from tests.support.solver_cases import solver_cases


def smokeview(left_end=10, right_start=0):
    text = ""
    for label, x, indices in [
        ("left", 0, [5, left_end, 1, 9, 0, 10]),
        ("right", 2, [right_start, 5, 1, 9, 0, 10]),
    ]:
        text += f"GRID {label}\n"
        for axis, tag in enumerate(["TRNX", "TRNY", "TRNZ"]):
            text += (
                tag
                + "\n0\n"
                + "".join(
                    f"{i} {x+i*0.2 if axis==0 else i*0.2:.5f}\n" for i in range(11)
                )
                + "\n"
            )
        text += (
            "OBST\n1\n0 0 0 0 0 0 1 ! wall\n"
            + " ".join(map(str, indices))
            + " -1 -1 ! F\n"
        )
    return text


def test_split_obstacle_is_verified_from_both_mesh_indices():
    gate = effective_obstructions(solver_cases()["multi_mesh"], smokeview())
    assert gate.status == "PASS", gate.reason
    assert len(gate.evidence["meshes"]) == 2
    assert gate.evidence["effective_bounds"]["wall"] == [1, 3, 0.2, 1.8, 0, 2]


def test_wrong_occupancy_in_one_mesh_is_rejected():
    gate = effective_obstructions(
        solver_cases()["multi_mesh"], smokeview(right_start=1)
    )
    assert gate.status == "FAIL"
    assert "right" in gate.reason


def test_missing_grid_and_nonadjacent_meshes_are_unproved():
    text = solver_cases()["multi_mesh"]
    assert effective_obstructions(text, "not solver output").status == "INCONCLUSIVE"
    gap = text.replace("XB=2,4,0,2,0,2", "XB=2.2,4.2,0,2,0,2")
    assert effective_obstructions(gap, smokeview()).status == "INCONCLUSIVE"


def test_cross_mesh_gap_cannot_silently_close():
    # Each mesh contains a separate wall. Nearest-cell snapping closes the
    # 0.12m opening at their interface; per-mesh inventory alone would pass.
    text = solver_cases()["multi_mesh"].replace(
        "&OBST ID='wall', XB=1,3,0.2,1.8,0,2 /",
        "&OBST ID='a', XB=1,1.94,0.2,1.8,0,2 /\n&OBST ID='b', XB=2.06,3,0.2,1.8,0,2 /",
    )
    smv = smokeview().replace("! wall", "! a", 1)
    position = smv.index("GRID right")
    smv = smv[:position] + smv[position:].replace("! wall", "! b")
    gate = effective_obstructions(text, smv)
    assert gate.status == "FAIL"
    assert "Passage closed across mesh interface" in gate.reason
