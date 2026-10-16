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
    assert result["report"]["gates"]["source_inventory"]["status"] == "PASS"
    assert result["report"]["gates"]["geometry"]["status"] == "PASS"
    assert result["manifest"]["acceptance_status"] == result["report"]["status"]
    assert client.get("/api/jobs/" + jid + "/artifacts/fds").status_code == 200


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
    assert client.get("/api/reference-cases").json() == {"cases": ["basement"]}
    assert configuration_value('{"reference_case":"basement"}')[
        "reference_case"
    ].endswith("basement-b1-b2")
