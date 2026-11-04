"""R10-07 — per-mode JSON result contracts and fail-closed API protection."""

import json
import threading
import time

import pytest

from ifc_to_fds.adapters.jobs.result_contract import validate_job_result
from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.core.canonical import SCHEMA_VERSION


def _artifact(filename):
    return {"filename": filename}


def valid_convert():
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "MAPPING_VERIFIED",
        "mapping_status": "MAPPING_VERIFIED",
        "simulation_status": "INCONCLUSIVE",
        "output_complete": True,
        "source_filename": "fixture.ifc",
        "profile": "mapping",
        "coverage": {},
        "timings": {},
        "gates": {
            name: {
                "status": "PASS", "required": True,
                "reason": "Independent verified gate: " + name,
                "reason_code": name.upper() + "_PASS",
            }
            for name in (
                "syntax", "source_inventory", "traceability", "scope",
                "geometry", "representation", "domain",
            )
        },
        "findings": [],
        "findings_count": 0,
        "blocker_count": 0,
        "research": {},
        "artifacts": {
            "fds": _artifact("model.fds"),
            "manifest": _artifact("model_manifest.json"),
            "report": _artifact("model_acceptance_report.json"),
            "geometry": _artifact("model_geometry.json"),
        },
    }


def valid_scenario():
    return {
        "status": "COMPLETED", "verdict": "INCONCLUSIVE",
        "verdict_reason": "Independent simulation not verified",
        "mesh_status": "PASS", "physics_status": "INCONCLUSIVE",
        "simulation_status": "NOT_RUN",
        "peak_hrr_mw": 4.5,
        "evidence": {"fds_sha256": "a" * 64, "physics": {"status": "INCONCLUSIVE"}},
        "artifacts": {"scenario_fds": _artifact("scenario.fds")},
        "scenario_id": "ev-1", "bundle_sha256": "b" * 64,
        "fds_file": "scenario.fds",
    }


def valid_preview():
    return {
        "status": "PREVIEW_ONLY", "verification": "NOT_RUN",
        "display_linear_deflection_m": 0.005, "total_elements": 4,
        "rendered_elements": 3, "failed_elements": 1,
        "bounds": None, "sources": [], "storeys": [],
        "artifacts": {"geometry": {}, "mep": {}},
    }


def valid_inventory():
    return {
        "total_elements": 2, "storeys": ["Ground"],
        "storey_references": [], "sources": [], "research": {},
    }


@pytest.mark.parametrize("mode,factory", [
    ("convert", valid_convert),
    ("scenario", valid_scenario),
    ("preview", valid_preview),
    ("inventory", valid_inventory),
])
def test_valid_mode_contract_retains_unmodified_document(mode, factory):
    doc = factory()
    doc["non_scientific_extension"] = {"label": "compatible"}
    assert validate_job_result(mode, doc) is doc


@pytest.mark.parametrize("mutation", [
    {"status": "SIMULATION_VERIFIED"},
    {"mapping_status": "INCONCLUSIVE"},
    {"output_complete": False},
    {"findings_count": 1},
    {"gates": {}},
    {"artifacts": {"fds": _artifact("model.fds")}},
    {"simulation_status": "SIMULATION_VERIFIED"},
    {"schema_version": "0.3.0"},
    {"status": 200},
    {"blocker_count": 1},
    {"gates": {"source_inventory": {
        "status": "PASS", "required": True,
        "reason": "One gate is insufficient", "reason_code": "SOURCE_PASS",
    }}},
])
def test_convert_cannot_publish_unsupported_or_unproven_verdict(mutation):
    doc = valid_convert()
    doc.update(mutation)
    with pytest.raises(ValueError):
        validate_job_result("convert", doc)


@pytest.mark.parametrize("mutation", [
    {"status": "PASS"},
    {"verdict": "PASS"},
    {"simulation_status": "SIMULATION_VERIFIED"},
    {"verdict": "FAIL"},
    {"mesh_status": "FAIL"},
    {"physics_status": "FAIL"},
    {"evidence": {}},
    {"artifacts": {}},
    {"peak_hrr_mw": float("nan")},
])
def test_scenario_requires_consistent_gates_and_evidence(mutation):
    doc = valid_scenario()
    doc.update(mutation)
    with pytest.raises(ValueError):
        validate_job_result("scenario", doc)


@pytest.mark.parametrize("mutation", [
    {"status": "MAPPING_VERIFIED"},
    {"verification": "PASS"},
    {"rendered_elements": 10},
    {"artifacts": {"fds": {}}},
])
def test_preview_cannot_claim_acceptance(mutation):
    doc = valid_preview()
    doc.update(mutation)
    with pytest.raises(ValueError):
        validate_job_result("preview", doc)


def test_inventory_must_have_structural_fields_and_no_scientific_status():
    doc = valid_inventory()
    assert validate_job_result("inventory", doc)["total_elements"] == 2
    with pytest.raises(ValueError):
        validate_job_result("inventory", {**doc, "status": "MAPPING_VERIFIED"})
    with pytest.raises(ValueError):
        validate_job_result("inventory", {"total_elements": 2})


@pytest.mark.parametrize("mode", ["unknown", "", "solver"])
def test_unknown_mode_fails_closed(mode):
    with pytest.raises(ValueError, match="Unsupported result mode"):
        validate_job_result(mode, {})


def test_artifact_names_cannot_be_redirected_or_renamed():
    doc = valid_convert()
    doc["artifacts"]["fds"]["filename"] = "../../other-job/secret.txt"
    with pytest.raises(ValueError, match="artifact descriptor"):
        validate_job_result("convert", doc)
    doc = valid_convert()
    doc["artifacts"]["fake"] = {"filename": "model.fds"}
    with pytest.raises(ValueError, match="artifact descriptor"):
        validate_job_result("convert", doc)


def test_read_result_revalidates_tampered_persisted_result(tmp_path):
    repository = JobRepository(root=tmp_path)
    directory = tmp_path / "job-1"
    directory.mkdir()
    doc = valid_convert()
    (directory / "result.json").write_text(json.dumps(doc), encoding="utf-8")
    repository.set("job-1", {
        "id": "job-1", "directory": str(directory),
        "state": "COMPLETED", "mode": "convert", "created": 0.0
    })
    response = repository.read_result("job-1")
    assert response["artifacts"]["fds"]["url"] == "/api/jobs/job-1/artifacts/fds"
    assert "url" not in doc["artifacts"]["fds"]
    doc["status"] = "SIMULATION_VERIFIED"
    (directory / "result.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        repository.read_result("job-1")
    (directory / "result.json").write_text('{"status": ', encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable result.json"):
        repository.read_result("job-1")


@pytest.mark.parametrize("mode,payload", [
    ("convert", {"status": "MAPPING_VERIFIED"}),
    ("convert", {**valid_convert(), "gates": {}}),
    ("scenario", {**valid_scenario(), "verdict": "PASS"}),
    ("scenario", {**valid_scenario(), "artifacts": {}}),
    ("preview", {"status": "PREVIEW_ONLY"}),
    ("inventory", {"total_elements": 3}),
])
def test_worker_completion_rejects_invalid_mode_specific_result(tmp_path, mode, payload):
    from ifc_to_fds.adapters.jobs.service import JobService

    service = JobService(root=tmp_path, max_waiting=1)
    job_id = "job-invalid"
    directory = tmp_path / job_id
    directory.mkdir()
    (directory / "result.json").write_text(json.dumps(payload), encoding="utf-8")

    class ExitedWorker:
        pid = None
        returncode = 0

        def poll(self):
            return 0

    service.repository.set(job_id, {
        "id": job_id, "mode": mode, "state": "RUNNING",
        "directory": str(directory), "created": time.time() - 10,
        "started": time.time() - 5, "process": ExitedWorker(),
        "durable": False,
    })
    worker = threading.Thread(target=service._loop, daemon=True)
    try:
        worker.start()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            job = service.repository.get(job_id)
            if job and job["state"] != "RUNNING":
                break
            time.sleep(0.05)
        job = service.repository.get(job_id)
        assert job is not None and job["state"] == "FAILED"
        assert job.get("durable") is not True
        assert "Invalid result.json" in job["error"]
        assert (directory / "diagnostics.json").is_file()
    finally:
        service.closed = True
        service.wake.set()
        worker.join(timeout=4)
        service.close()


def test_preview_urls_remain_available_after_validation(tmp_path):
    repository = JobRepository(root=tmp_path)
    directory = tmp_path / "job-preview"
    directory.mkdir()
    (directory / "result.json").write_text(json.dumps(valid_preview()), encoding="utf-8")
    repository.set("job-preview", {
        "id": "job-preview", "directory": str(directory),
        "state": "COMPLETED", "mode": "preview", "created": 0.0,
    })
    res = repository.read_result("job-preview")
    assert res["artifacts"]["geometry"]["url"] == "/api/jobs/job-preview/artifacts/geometry"
    assert res["artifacts"]["mep"]["url"] == "/api/jobs/job-preview/artifacts/mep"
