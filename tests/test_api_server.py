import os
from fastapi.testclient import TestClient
from ifc_to_fds.server import app

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
client = TestClient(app)


def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ifc_to_fds"


def test_api_inventory():
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    with open(fzk_path, "rb") as f:
        response = client.post(
            "/api/inventory",
            files={"file": ("AC20-FZK-Haus.ifc", f, "application/octet-stream")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["total_elements"] == 110
    assert "Erdgeschoss" in data["storeys"]
    assert "Dachgeschoss" in data["storeys"]


def test_api_convert():
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    with open(fzk_path, "rb") as f:
        response = client.post(
            "/api/convert",
            files={"file": ("AC20-FZK-Haus.ifc", f, "application/octet-stream")},
            data={"cell_size": "0.2", "all_geom": "true"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "VERIFIED"
    assert "&HEAD CHID='AC20-FZK-Haus'" in data["fds_text"]
    assert data["manifest"] is not None
    assert data["report"] is not None
    assert "Acceptance Report" in data["markdown_report"]
