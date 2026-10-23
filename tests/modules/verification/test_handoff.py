import pytest

from ifc_to_fds.modules.verification.api import summarize_handoff
from scripts.prepare_pyrosim_acceptance import main
from tests.support.solver_cases import solver_cases


def complete():
    return {
        name: {"status": "PASS"}
        for name in (
            "syntax",
            "mapping",
            "setup_solver",
            "cold_flow",
            "roundtrip_geometry",
            "roundtrip_solver",
            "pyrosim_import",
            "effective_geometry",
            "roundtrip_effective_geometry",
        )
    }


def test_effective_geom_uncertainty_cannot_be_hidden_by_editor_handoff():
    report = complete()
    report["effective_geometry"]["status"] = "INCONCLUSIVE"
    handoff, verification = summarize_handoff(report)
    assert handoff["status"] == "PASS"
    assert verification["status"] == "INCONCLUSIVE"
    assert verification["pending"] == ["effective_geometry"]
    assert verification["simulation"] == "NOT_VERIFIED"


@pytest.mark.parametrize("name", list(complete()))
def test_any_missing_required_evidence_blocks_full_verification(name):
    report = complete()
    del report[name]
    _, verification = summarize_handoff(report)
    assert verification["status"] != "PASS"
    assert name in verification["pending"]


def test_fail_takes_priority_over_missing_gui():
    report = complete()
    report["pyrosim_import"]["status"] = "BLOCKED"
    report["effective_geometry"]["status"] = "FAIL"
    assert summarize_handoff(report)[1]["status"] == "FAIL"


def test_complete_static_evidence_is_scoped_and_does_not_verify_fire_physics():
    handoff, verification = summarize_handoff(complete())
    assert handoff["status"] == verification["status"] == "PASS"
    assert verification["simulation"] == "NOT_VERIFIED"


def test_packet_never_overwrites_the_supplied_reexport(tmp_path):
    original = tmp_path / "model.fds"
    original.write_text(solver_cases()["obst"])
    output = tmp_path / "packet"
    output.mkdir()
    exported = output / original.name
    exported.write_text("important re-export evidence")
    before = exported.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        main([str(original), "--output", str(output), "--roundtrip", str(exported)])
    assert exported.read_bytes() == before
