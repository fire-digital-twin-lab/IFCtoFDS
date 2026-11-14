"""A grid too coarse for an opening or a thin wall is reported by name with the cell size that fixes it."""

from pathlib import Path

from ifc_to_fds.pipeline import convert

OPENING = str(Path(__file__).parent / "baseline" / "fixtures" / "opening.ifc")


def _resolution(result):
    gate = result["report"]["gates"]["passage_resolution"]
    findings = [f for f in result["report"]["findings"] if f["category"] == "passage_resolution"]
    return gate, findings


def test_default_grid_resolves_the_opening_fixture():
    gate, findings = _resolution(convert([OPENING], configuration={"cell_size": 0.2}))
    assert gate["status"] == "PASS" and not findings


def test_coarse_grid_fails_by_name_and_proposes_a_cell_size():
    result = convert([OPENING], configuration={"cell_size": 1.0})
    gate, findings = _resolution(result)
    assert gate["status"] == "FAIL", gate
    assert findings and all(f["verification_level"] == "simulation" for f in findings)
    assert any("Use cells of at most" in f["detail"] for f in findings)
    # The mapping is still right; only the simulation cannot rely on this grid.
    assert result["mapping_status"] == "MAPPING_VERIFIED"
    assert result["simulation_status"] == "REJECTED"
    ok = convert([OPENING], configuration={"cell_size": 0.2})
    assert ok["simulation_status"] == "INCONCLUSIVE"  # unchanged when the grid resolves everything


def test_proposed_cell_size_actually_resolves_the_passage():
    coarse = convert([OPENING], configuration={"cell_size": 1.0})
    _, findings = _resolution(coarse)
    sizes = [float(f["detail"].rsplit("at most ", 1)[1].split(" ")[0]) for f in findings if "narrower" in f["title"]]
    assert sizes, findings
    gate, _ = _resolution(convert([OPENING], configuration={"cell_size": min(sizes)}))
    assert gate["status"] == "PASS", gate
