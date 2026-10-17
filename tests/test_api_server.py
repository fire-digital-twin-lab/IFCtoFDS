import time
import pytest
from fastapi.testclient import TestClient
from ifc_to_fds.server import app

client = TestClient(app)


def test_api_health_and_private_paths():
    assert client.get("/api/health").json()["status"] == "ok"
    for path in ("/.git/config", "/pyproject.toml", "/ifc_to_fds/server.py"):
        assert client.get(path).status_code == 404


def test_api_inventory(tiny_ifc):
    path, _, _ = tiny_ifc
    response = client.post(
        "/api/inventory", files={"file": ("tiny.ifc", path.read_bytes())}
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_elements"] == 2
    assert response.json()["storey_references"][0]["name"] == "Ground"


def test_api_convert_job(tiny_ifc):
    path, _, _ = tiny_ifc
    response = client.post(
        "/api/jobs", files=[("files", ("tiny.ifc", path.read_bytes()))]
    )
    assert response.status_code == 202, response.text
    jid = response.json()["id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        job = client.get("/api/jobs/" + jid).json()
        if job["state"] in ("COMPLETED", "FAILED", "TIMED_OUT"):
            break
        time.sleep(0.1)
    assert job["state"] == "COMPLETED", job
    result = client.get("/api/jobs/" + jid + "/result").json()
    assert result["status"] == "MAPPING_VERIFIED"
    assert result["simulation_status"] == "INCONCLUSIVE"
    assert result["gates"]["source_inventory"]["status"] == "PASS"
    assert result["gates"]["geometry"]["status"] == "PASS"
    assert "geometry_package" not in result and "fds_text" not in result
    manifest = client.get(result["artifacts"]["manifest"]["url"]).json()
    assert manifest["acceptance_status"] == result["status"]
    assert client.get("/api/jobs/" + jid + "/artifacts/fds").status_code == 200
    index = client.get(result["artifacts"]["geometry"]["url"]).json()
    ref = next(e["mesh"] for e in index["elements"].values() if e["mesh"])
    payload = client.get("/api/jobs/" + jid + "/geometry/" + ref["payload"])
    import hashlib

    assert hashlib.sha256(payload.content).hexdigest() == ref["payload"]
    assert client.get("/api/jobs/" + jid + "/geometry/" + "0" * 64).status_code == 404
    assert "_geometry_payloads" not in client.get("/api/jobs/" + jid).json()
    assert client.get(result["artifacts"]["geometry_archive"]["url"]).status_code == 200


@pytest.mark.parametrize("cell", ["0", "-1", "nan", "inf"])
def test_invalid_cell_size(cell):
    response = client.post(
        "/api/convert",
        files={"file": ("tiny.ifc", b"not parsed")},
        data={"cell_size": cell},
    )
    assert response.status_code == 422


def test_cross_origin_and_upload_limit(monkeypatch):
    assert (
        client.post(
            "/api/jobs",
            headers={"Origin": "https://other.example"},
            files={"files": ("tiny.ifc", b"abc")},
        ).status_code
        == 403
    )
    monkeypatch.setattr("ifc_to_fds.server.MAX_FILE", 2)
    assert (
        client.post("/api/jobs", files={"files": ("tiny.ifc", b"123")}).status_code
        == 413
    )


@pytest.mark.parametrize(
    "configuration",
    [
        '{"scope":{"boundingBox":[0,1,0,1,0,1]}}',
        '{"all_geom":"false"}',
        '{"sources":{"common_coordinates":"yes"}}',
        '{"skip_validation":true}',
        '{"audit":{"surface_tolernce_m":1.0}}',
    ],
)
def test_unknown_or_mistyped_configuration_rejected(configuration):
    response = client.post(
        "/api/jobs",
        files={"files": ("tiny.ifc", b"not parsed")},
        data={"configuration": configuration},
    )
    assert response.status_code == 422


def test_reference_paths_are_operator_registered(monkeypatch):
    from ifc_to_fds.server import configuration_value
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        configuration_value('{"reference_case":"C:/private/model"}')
    monkeypatch.setenv(
        "IFCFDS_REFERENCE_CASES", '{"basement":"reference-cases/basement-b1-b2"}'
    )
    cases = client.get("/api/reference-cases").json()["cases"]
    assert cases[0]["id"] == "basement" and cases[0]["approval_status"] == "DRAFT"
    assert "path" not in cases[0]
    assert configuration_value('{"reference_case":"basement"}')[
        "reference_case"
    ].endswith("basement-b1-b2")


def test_research_recognition_does_not_select_or_accept_profile(monkeypatch):
    from ifc_to_fds.results import research_context

    monkeypatch.setattr(
        "ifc_to_fds.results.registered_cases",
        lambda: [
            dict(
                id="basement",
                name="B1/B2",
                source_hashes=["a", "b"],
                approval_status="DRAFT",
            )
        ],
    )
    partial = research_context([dict(file_hash_sha256="a")], {"profile": "mapping"})
    assert partial["known_cases"][0]["source_match"] == "PARTIAL"
    assert partial["parity_status"] == "NOT_RUN"
    assert partial["research_acceptance"] == "NOT_RUN"
    exact = research_context(
        [dict(file_hash_sha256=x) for x in ("a", "b")], {"profile": "mapping"}
    )
    assert exact["known_cases"][0]["source_match"] == "EXACT"
    assert exact["research_acceptance"] == "NOT_RUN"


def test_geometry_payload_returns_404_when_index_file_missing(tmp_path):
    from ifc_to_fds.server import manager

    job_id = "test-job-no-geometry"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "state": "COMPLETED",
        "directory": str(tmp_path),
    }
    dummy_payload = "a" * 64
    response = client.get(f"/api/jobs/{job_id}/geometry/{dummy_payload}")
    assert response.status_code == 404
    assert "Geometry index not available" in response.json()["detail"]


def test_checkpoint_artifacts_accessible_on_failed_or_incomplete_jobs(tmp_path):
    from ifc_to_fds.server import manager

    job_id = "test-job-failed-audit"
    (tmp_path / "model.fds").write_text("&HEAD CHID='test' /", encoding="utf-8")
    manager.jobs[job_id] = {
        "job_id": job_id,
        "state": "FAILED",
        "directory": str(tmp_path),
    }
    # Regular /artifacts requires COMPLETED
    res_reg = client.get(f"/api/jobs/{job_id}/artifacts/fds")
    assert res_reg.status_code == 409

    # /checkpoints allows access with unaccepted header
    res_chk = client.get(f"/api/jobs/{job_id}/checkpoints/fds")
    assert res_chk.status_code == 200
    assert "&HEAD" in res_chk.text
    assert (
        res_chk.headers.get("X-Verification-Status")
        == "UNACCEPTED-AUDIT_INCOMPLETE-DO_NOT_USE_AS_VERIFIED_OUTPUT"
    )


