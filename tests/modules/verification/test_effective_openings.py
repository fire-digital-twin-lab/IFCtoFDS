"""Native SMV fixtures plus mutations of actual integer solver output."""

from pathlib import Path
import re

import pytest

from ifc_to_fds.modules.verification.application.effective_obstructions import (
    effective_obstructions,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/solver/fds-6.11.1"


def texts(name):
    return tuple(
        (FIXTURES / (name + suffix)).read_text(encoding="utf-8")
        for suffix in (".fds", ".smv")
    )


@pytest.mark.parametrize("name", ["hole", "vent"])
def test_native_smv_opening_and_vent_evidence_passes(name):
    gate = effective_obstructions(*texts(name))
    assert gate.status == "PASS", gate.reason
    assert gate.evidence["obstacles"]["wall"]["mismatched_cells"] == 0
    if name == "hole":
        assert gate.evidence["obstacles"]["wall"]["effective_cells"] == 520
        assert gate.evidence["openings"]["opening"]["blocked_cells"] == 0
    else:
        assert gate.evidence["vents"]["outside"]["surface"] == "OPEN"
        assert gate.evidence["vents"]["outside"]["adjacent_cells_clear"]


def test_closing_hole_in_solver_integer_table_is_rejected():
    text, smv = texts("hole")
    changed, count = re.subn(
        r"(?m)^(\s*5\s+15\s+3\s+7\s+)7(\s+10\s+)", r"\g<1>0\2", smv
    )
    assert count == 1
    gate = effective_obstructions(text, changed)
    assert gate.status == "FAIL"
    assert gate.evidence["obstacles"]["wall"]["mismatched_cells"] == 280


@pytest.mark.parametrize(
    "mutation", ["footprint", "surface", "identity", "missing_table", "ungridded"]
)
def test_vent_mutations_cannot_receive_effective_pass(mutation):
    text, smv = texts("vent")
    lines = smv.splitlines()
    if mutation in ("surface", "footprint"):
        start = lines.index("VENT") + 1
        count = int(lines[start].split()[0])
        index = start + 1 if mutation == "surface" else start + 1 + count
        fields = lines[index].split()
        fields[7 if mutation == "surface" else 3] = (
            "0" if mutation == "surface" else "9"
        )
        lines[index] = " ".join(fields)
        smv = "\n".join(lines)
    elif mutation == "identity":
        smv = smv.replace("! outside", "! unexpected")
    elif mutation == "missing_table":
        smv = smv.replace("\nTRNZ\n", "\nREMOVED\n")
    else:
        text = text.replace("XB=0,0,0,2,0,2", "XB=0,0,0.01,2,0,2")
    assert effective_obstructions(text, smv).status != "PASS"


def test_hole_adapter_resource_limit_does_not_allocate_unbounded_cell_arrays():
    text, smv = texts("hole")
    text = text.replace("IJK=20,10,10", "IJK=2000,2000,2000")
    assert effective_obstructions(text, smv).status == "INCONCLUSIVE"
