"""R10-08: test persisted evidence against post-completion tampering."""

import hashlib
import threading
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
    with pytest.raises(ValueError, match="Missing evidence index: historical or incomplete job"):
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

    # Recomputing the index must not hide a report that contradicts the
    # independently sealed mapping status in the manifest and checkpoint.
    report = json.loads(report_path.read_text("utf-8"))
    report["status"] = "REJECTED"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="Acceptance report status contradicts"):
        build_evidence_index(directory, "convert", public)

    # Geometry bytes and the original manifest package digest must agree
    # even if a new index is requested after the geometry file was changed.
    report["status"] = public["status"]
    report_path.write_text(json.dumps(report), encoding="utf-8")
    geometry_path = directory / "model_geometry.json"
    geometry = json.loads(geometry_path.read_text("utf-8"))
    geometry["sha256"] = "0" * 64
    geometry_path.write_text(json.dumps(geometry), encoding="utf-8")
    with pytest.raises(ValueError, match="Geometry index differs"):
        build_evidence_index(directory, "convert", public)


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


def test_legacy_completed_result_cannot_be_read_or_silently_resealed(tmp_path):
    result = _scenario(tmp_path)
    (tmp_path / "result_evidence.json").unlink()
    repository = JobRepository(root=tmp_path)
    repository.set("legacy-job", {
        "id": "legacy-job", "state": "COMPLETED", "mode": "scenario",
        "directory": str(tmp_path), "created": 0,
    })
    with pytest.raises(ValueError, match="read-only provenance review required"):
        repository.read_result("legacy-job")
    assert not (tmp_path / "result_evidence.json").exists()


def test_scenario_integrity_hashes_each_file_once(monkeypatch, tmp_path):
    from ifc_to_fds.adapters.jobs import evidence_index

    result = _scenario(tmp_path)
    original = evidence_index._sha256
    paths = []

    def counted(path):
        paths.append(path.name)
        return original(path)

    monkeypatch.setattr(evidence_index, "_sha256", counted)
    verify_evidence_index(tmp_path, "scenario", result)
    assert sorted(paths) == ["result.json", "scenario.fds"]


def test_inconclusive_conversion_report_must_match_result(tmp_path):
    result = {
        "status": "INCONCLUSIVE",
        "mapping_status": "INCONCLUSIVE",
        "simulation_status": "INCONCLUSIVE",
        "output_complete": False,
        "artifacts": {
            "manifest": {"filename": "model_manifest.json"},
            "report": {"filename": "model_acceptance_report.json"},
        },
    }
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")
    manifest = {
        "acceptance_status": "INCONCLUSIVE",
        "mapping_acceptance": "INCONCLUSIVE",
        "simulation_acceptance": "INCONCLUSIVE",
        "output_complete": False,
    }
    report = {
        "status": "INCONCLUSIVE",
        "mapping_status": "INCONCLUSIVE",
        "simulation_status": "INCONCLUSIVE",
    }
    (tmp_path / "model_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report_path = tmp_path / "model_acceptance_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    write_evidence_index(tmp_path, "convert", result)
    verify_evidence_index(tmp_path, "convert", result)
    report["mapping_status"] = "REJECTED"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="Acceptance report mapping_status contradicts"):
        build_evidence_index(tmp_path, "convert", result)


def test_service_result_does_not_hold_scheduler_lock_during_file_io(
    tmp_path, monkeypatch
):
    from ifc_to_fds.adapters.jobs.service import JobService

    service = JobService(root=tmp_path)
    service.repository.set("snapshot-job", {
        "id": "snapshot-job",
        "state": "COMPLETED",
        "directory": str(tmp_path),
        "mode": "scenario",
        "created": 0,
    })
    observed = []

    def inspect_read(jid, *, job=None):
        assert jid == "snapshot-job"
        assert job is not None and job["state"] == "COMPLETED"

        def probe():
            acquired = service.lock.acquire(timeout=1.0)
            observed.append(acquired)
            if acquired:
                service.lock.release()

        probe_thread = threading.Thread(target=probe)
        probe_thread.start()
        probe_thread.join(timeout=2)
        assert not probe_thread.is_alive()
        return {"verified": False}

    monkeypatch.setattr(service.repository, "read_result", inspect_read)
    try:
        assert service.result("snapshot-job") == {"verified": False}
        assert observed == [True]
    finally:
        service.close()
