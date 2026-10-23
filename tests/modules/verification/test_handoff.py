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


@pytest.mark.parametrize("shift", [0, 0.0005])
@pytest.mark.parametrize("override", [False, True])
def test_manifest_tolerances_apply_to_mapping_roundtrip_and_every_solver_run(
    tiny_ifc, tmp_path, monkeypatch, shift, override
):
    import json
    from ifc_to_fds.pipeline import convert, save_artifacts
    from ifc_to_fds.domain.validation import GateResult
    from ifc_to_fds.modules.verification.api import compare_roundtrip_geometry
    import scripts.prepare_pyrosim_acceptance as command

    source, _, _ = tiny_ifc
    approved = {"surface_tolerance_m": 0.00001, "solver_timeout_s": 17.0}
    result = convert([source], {"audit": approved}, output_directory=tmp_path / "convert")
    original = tmp_path / "source.fds"
    save_artifacts(result, original)
    text = original.read_text(encoding="utf-8")
    exported = tmp_path / "export.fds"
    # The authored wall is 2 x 1 x 3 m; 0.5 mm passes default solid tolerances.
    import re
    def move(match):
        values = list(map(float, match[2].split(",")))
        values[0] += shift
        values[1] += shift
        return match[1] + ",".join(map(str, values))
    changed, count = re.subn(r"(&OBST[^/]*?XB=)((?:[-+\deE.]+,){5}[-+\deE.]+)", move, text)
    assert count == 1
    exported.write_text(changed, encoding="utf-8")
    if shift:
        assert compare_roundtrip_geometry(text, changed).status == "PASS"
    seen = []
    def solver(text, config):
        seen.append(config)
        return (GateResult(status="PASS", evidence={"completion": {"mode": "SETUP_ONLY"}}), GateResult(status="PASS"))
    monkeypatch.setattr(command, "solver_gates", solver)
    # Mapping's engine uses its injected native runner; capture its resolved
    # configuration while leaving real independent mapping checks enabled.
    import ifc_to_fds.pipeline as pipeline
    real_audit = pipeline.audit
    mappings = []
    def audit(*args, **kwargs):
        mappings.append(args[3]["audit"])
        return real_audit(*args, **kwargs)
    monkeypatch.setattr(pipeline, "audit", audit)
    output = tmp_path / "packet"
    arguments = [str(original), "--output", str(output), "--ifc", str(source),
                 "--manifest", str(tmp_path / "source_manifest.json"),
                 "--geometry-package", str(tmp_path / "source_geometry.json"),
                 "--roundtrip", str(exported), "--solver", "unavailable-test-solver"]
    if override:
        path = tmp_path / "override.json"
        path.write_text('{"solver_timeout_s": 23}', encoding="utf-8")
        arguments += ["--audit-config", str(path)]
    main(arguments)
    report = json.loads((output / "acceptance.json").read_text(encoding="utf-8"))
    assert mappings[0]["surface_tolerance_m"] == 0.00001
    assert seen and all(c.surface_tolerance_m == 0.00001 for c in seen)
    assert all(c.solver_timeout_s == (23 if override else 17) for c in seen)
    assert report["roundtrip_geometry"]["status"] == ("FAIL" if shift else "PASS")
    assert report["audit_configuration"]["resolved"]["surface_tolerance_m"] == 0.00001
    assert len(seen) == (1 if shift else 3)  # cold run, plus both re-export runs
