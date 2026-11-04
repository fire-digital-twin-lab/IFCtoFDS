"""Acceptance audit is read-only and must never promote scientific verdicts."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ifc_to_fds.adapters.jobs.acceptance_audit import audit_persisted_job
from ifc_to_fds.adapters.jobs.evidence_index import write_evidence_index


@pytest.fixture
def scenario_job(tmp_path):
    fds = b"&HEAD CHID='evidence-audit' /\n&TAIL /\n"
    (tmp_path / "scenario.fds").write_bytes(fds)
    data = {
        "status": "COMPLETED",
        "verdict": "INCONCLUSIVE",
        "verdict_reason": "No independent CFD simulation verification",
        "mesh_status": "PASS",
        "physics_status": "INCONCLUSIVE",
        "simulation_status": "NOT_RUN",
        "peak_hrr_mw": 2.0,
        "evidence": {
            "fds_sha256": hashlib.sha256(fds).hexdigest(),
            "physics": {"status": "INCONCLUSIVE"},
        },
        "artifacts": {"scenario_fds": {"filename": "scenario.fds"}},
        "scenario_id": "EV-1",
        "bundle_sha256": "b" * 64,
        "fds_file": "scenario.fds",
    }
    (tmp_path / "result.json").write_text(json.dumps(data), encoding="utf-8")
    write_evidence_index(tmp_path, "scenario", data)
    return tmp_path


def test_audit_valid_scenario_is_not_simulation_approval(scenario_job):
    before = {
        path.name: path.read_bytes() for path in scenario_job.iterdir() if path.is_file()
    }
    audit = audit_persisted_job(scenario_job, "scenario")
    assert audit["audit_outcome"] == "EVIDENCE_VALID"
    assert audit["checks"]["result_contract"]["status"] == "PASS"
    assert audit["checks"]["evidence_integrity"]["status"] == "PASS"
    assert audit["checks"]["solver_verification"]["status"] == "NOT_RUN"
    assert audit["reported_verdict"] == "INCONCLUSIVE"
    assert audit["scientific_acceptance"] == "NOT_ESTABLISHED_BY_THIS_AUDIT"
    after = {
        path.name: path.read_bytes() for path in scenario_job.iterdir() if path.is_file()
    }
    assert before == after, "Audit cannot modify the sealed job directory"


@pytest.mark.parametrize("broken", ["result.json", "scenario.fds", "result_evidence.json"])
def test_audit_detects_changed_persisted_evidence(scenario_job, broken):
    target = scenario_job / broken
    target.write_bytes(target.read_bytes() + b"\nchanged")
    audit = audit_persisted_job(scenario_job, "scenario")
    assert audit["audit_outcome"] == "INTEGRITY_INVALID"
    assert audit["checks"]["evidence_integrity"]["status"] == "FAIL" or (
        audit["checks"]["result_contract"]["status"] == "FAIL"
    )


def test_audit_missing_historical_index_is_not_resealed(scenario_job):
    evidence = scenario_job / "result_evidence.json"
    evidence.unlink()
    result = audit_persisted_job(scenario_job, "scenario")
    assert result["audit_outcome"] == "INTEGRITY_INVALID"
    assert result["checks"]["evidence_integrity"]["status"] == "FAIL"
    assert not evidence.exists()


def test_audit_rejects_unsupported_scientific_pass(scenario_job):
    path = scenario_job / "result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["verdict"] = "PASS"
    path.write_text(json.dumps(data), encoding="utf-8")
    audit = audit_persisted_job(scenario_job, "scenario")
    assert audit["audit_outcome"] == "INTEGRITY_INVALID"
    assert audit["checks"]["result_contract"]["status"] == "FAIL"


def test_audit_preserves_rejected_scenario_even_with_intact_hashes(scenario_job):
    result_path = scenario_job / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["verdict"] = "FAIL"
    result["mesh_status"] = "FAIL"
    result["verdict_reason"] = "Mesh resolution check failed"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    write_evidence_index(scenario_job, "scenario", result)

    audit = audit_persisted_job(scenario_job, "scenario")
    assert audit["audit_outcome"] == "EVIDENCE_VALID"
    assert audit["reported_verdict"] == "FAIL"
    assert audit["checks"]["solver_verification"]["status"] == "NOT_RUN"
    assert audit["scientific_acceptance"] == "NOT_ESTABLISHED_BY_THIS_AUDIT"


def test_untrusted_verdict_is_not_echoed_as_nested_json(scenario_job):
    path = scenario_job / "result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["verdict"] = {"unexpected": ["not a verdict"]}
    path.write_text(json.dumps(data), encoding="utf-8")
    report = audit_persisted_job(scenario_job, "scenario")
    assert report["reported_verdict"] is None
    assert report["checks"]["result_contract"]["status"] == "FAIL"


def test_inventory_audit_never_claims_scientific_verification(tmp_path):
    document = {
        "total_elements": 1,
        "storeys": [],
        "storey_references": [],
        "sources": [],
        "research": {},
    }
    (tmp_path / "result.json").write_text(json.dumps(document), encoding="utf-8")
    audit = audit_persisted_job(tmp_path, "inventory")
    assert audit["audit_outcome"] == "STRUCTURE_VALID"
    assert audit["checks"]["evidence_integrity"]["status"] == "NOT_APPLICABLE"
    assert audit["checks"]["solver_verification"]["status"] == "NOT_RUN"
    assert audit["reported_verdict"] is None


def test_missing_or_invalid_json_is_a_failed_audit(tmp_path):
    assert audit_persisted_job(tmp_path, "scenario")["audit_outcome"] == "INTEGRITY_INVALID"
    (tmp_path / "result.json").write_text('{"broken":', encoding="utf-8")
    audit = audit_persisted_job(tmp_path, "scenario")
    assert audit["checks"]["result_json"]["status"] == "FAIL"


def test_geometry_payload_duplicate_and_offset_consistency(tmp_path, monkeypatch):
    from ifc_to_fds.adapters.jobs import acceptance_audit
    from ifc_to_fds.core.canonical import SCHEMA_VERSION
    from ifc_to_fds.geometry.package_integrity import seal

    binary = b"\\x00" * 36
    identity = hashlib.sha256(binary).hexdigest()
    geometry = tmp_path / "model_geometry.json"
    payload_dir = tmp_path / "model_geometry.payloads"
    payload_dir.mkdir()
    (payload_dir / (identity + ".bin")).write_bytes(binary)
    ref = {
        "payload": identity,
        "vertex_count": 1,
        "face_count": 1,
        "vertices_offset": 0,
        "faces_offset": 24,
        "byte_length": 36,
    }
    model = {
        "schema_version": SCHEMA_VERSION,
        "storage_format": "float64-uint32-le-v1",
        "units": "METRE",
        "coordinate_frame": "COMMON_WORLD",
        "elements": {
            "first": {"mesh": ref, "openings": {"duplicate": dict(ref)}},
        },
    }
    geometry.write_text(json.dumps(seal(model)), encoding="utf-8")
    original = acceptance_audit.file_hash
    hashed = []

    def counted(path):
        hashed.append(path.name)
        return original(path)

    monkeypatch.setattr(acceptance_audit, "file_hash", counted)
    assert acceptance_audit._verify_geometry_payloads(tmp_path) == 1
    assert hashed == [identity + ".bin"]

    # Re-sealing a damaged index is not sufficient: reference offsets
    # must still be internally consistent before a payload can be trusted.
    model["elements"]["first"]["mesh"] = dict(ref, faces_offset=12)
    geometry.write_text(json.dumps(seal(model)), encoding="utf-8")
    with pytest.raises(ValueError, match="offsets are inconsistent"):
        acceptance_audit._verify_geometry_payloads(tmp_path)


def test_read_only_cli_exit_status_is_not_scientific_pass(scenario_job):
    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "scripts" / "audit_job_acceptance.py"),
        str(scenario_job),
        "--mode",
        "scenario",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["audit_outcome"] == "EVIDENCE_VALID"
    assert document["checks"]["solver_verification"]["status"] == "NOT_RUN"

    (scenario_job / "result_evidence.json").unlink()
    invalid = subprocess.run(command, capture_output=True, text=True, check=False)
    assert invalid.returncode == 2, invalid.stderr
    assert json.loads(invalid.stdout)["audit_outcome"] == "INTEGRITY_INVALID"
