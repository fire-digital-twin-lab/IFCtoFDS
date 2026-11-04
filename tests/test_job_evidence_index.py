"""R10-08: test persisted evidence against post-completion tampering."""

import hashlib
import json

import pytest

from ifc_to_fds.adapters.jobs.evidence_index import (
    build_evidence_index,
    verify_evidence_index,
    write_evidence_index,
)
from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.pipeline import convert, save_artifacts
from ifc_to_fds.results import public_result


def scenario_result(data: bytes) -> dict:
    return {
        "status": "COMPLETED",
        "verdict": "INCONCLUSIVE",
        "verdict_reason": "CFD has not been independently verified",
        "mesh_status": "PASS",
        "physics_status": "INCONCLUSIVE",
        "simulation_status": "NOT_RUN",
        "peak_hrr_mw": 4.5,
        "evidence": {
            "fds_sha256": hashlib.sha256(data).hexdigest(),
            "physics": {"status": "INCONCLUSIVE"},
        },
        "artifacts": {"scenario_fds": {"filename": "scenario.fds"}},
        "scenario_id": "EV1",
        "bundle_sha256": "a" * 64,
        "fds_file": "scenario.fds",
    }


def _scenario(tmp_path):
    data = b"&HEAD CHID='evidence' /\n&TAIL /\n"
    (tmp_path / "scenario.fds").write_bytes(data)
    result = scenario_result(data)
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")
    write_evidence_index(tmp_path, "scenario", result)
    return result


def test_scenario_index_round_trip(tmp_path):
    result = _scenario(tmp_path)
    index = json.loads((tmp_path / "result_evidence.json").read_text("utf-8"))
    assert index["mode"] == "scenario"
    assert set(index["files"]) == {"scenario.fds", "result.json"}
    verify_evidence_index(tmp_path, "scenario", result)
    assert not list(tmp_path.glob("result_evidence.json.*.tmp"))


@pytest.mark.parametrize("target", ["scenario.fds", "result.json", "result_evidence.json"])
def test_tampered_scenario_evidence_is_rejected(tmp_path, target):
    result = _scenario(tmp_path)
    path = tmp_path / target
    path.write_bytes(path.read_bytes() + b"\nchanged")
    with pytest.raises(ValueError):
        verify_evidence_index(tmp_path, "scenario", result)


def test_missing_index_is_rejected(tmp_path):
    result = _scenario(tmp_path)
    (tmp_path / "result_evidence.json").unlink()
    with pytest.raises(ValueError, match="Cannot parse required evidence"):
        verify_evidence_index(tmp_path, "scenario", result)


def test_conflicting_fds_digest_cannot_be_indexed(tmp_path):
    data = b"&HEAD CHID='different' /\n"
    (tmp_path / "scenario.fds").write_bytes(data)
    result = scenario_result(data)
    result["evidence"]["fds_sha256"] = "f" * 64
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="FDS bytes differ"):
        build_evidence_index(tmp_path, "scenario", result)
    assert not (tmp_path / "result_evidence.json").exists()


def test_completed_scenario_read_checks_mutated_artifact(tmp_path):
    result = _scenario(tmp_path)
    repository = JobRepository(root=tmp_path)
    repository.set("job-1", {
        "id": "job-1", "state": "COMPLETED", "mode": "scenario",
        "directory": str(tmp_path), "created": 0,
    })
    assert repository.read_result("job-1")["verdict"] == "INCONCLUSIVE"
    (tmp_path / "scenario.fds").write_bytes(b"attacker-replaced-payload")
    with pytest.raises(ValueError, match="Evidence file changed"):
        repository.read_result("job-1")


def test_real_verified_conversion_evidence_is_consistent(tiny_ifc, tmp_path):
    source_path, _, _ = tiny_ifc
    directory = tmp_path / "verified"
    directory.mkdir()
    result = convert([str(source_path)], {
        "simulation_domain": {
            "xmin": 0, "xmax": 10,
            "ymin": 0, "ymax": 10,
            "zmin": 0, "zmax": 4,
        },
    }, directory)
    assert result["status"] == "MAPPING_VERIFIED", result["status"]
    save_artifacts(result, directory / "model.fds")
    public = public_result(result, directory=directory)
    (directory / "result.json").write_text(json.dumps(public), encoding="utf-8")
    write_evidence_index(directory, "convert", public)
    verify_evidence_index(directory, "convert", public)

    # Hashes include the persisted independent acceptance report and manifest.
    index = json.loads((directory / "result_evidence.json").read_text("utf-8"))
    assert "model_acceptance_report.json" in index["files"]
    assert "audit-state.json" in index["files"]
    assert "model_manifest.json" in index["files"]

    report_path = directory / "model_acceptance_report.json"
    report_path.write_text(report_path.read_text("utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Evidence file changed"):
        verify_evidence_index(directory, "convert", public)


def test_unverified_simulation_profile_is_not_falsely_sealed(tmp_path):
    # This contract tests the distinction between mapping_status and the
    # overall verdict used to determine whether the checkpoint is sealed.
    result = {
        "status": "INCONCLUSIVE",
        "mapping_status": "MAPPING_VERIFIED",
        "simulation_status": "INCONCLUSIVE",
        "artifacts": {},
    }
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")
    index = build_evidence_index(tmp_path, "convert", result)
    assert set(index["files"]) == {"result.json"}
    assert not (tmp_path / "audit-state.json").exists()
