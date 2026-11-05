"""Regression: a dead scheduler must not be reported healthy by its probe."""

import threading

import pytest
from fastapi.testclient import TestClient

from ifc_to_fds import server
from ifc_to_fds.adapters.jobs.readiness import is_scheduler_healthy


class FakeRepository:
    def __init__(self, pending=0):
        self.pending = pending

    def count_pending(self):
        return self.pending


class FakeThread:
    def __init__(self, alive):
        self.alive = alive

    def is_alive(self):
        return self.alive


class FakeService:
    def __init__(self, *, closed=False, pending=0, alive=None):
        self.lock = threading.RLock()
        self.closed = closed
        self.repository = FakeRepository(pending)
        self.thread = None if alive is None else FakeThread(alive)


@pytest.mark.parametrize(
    "closed,pending,alive,expected",
    [
        (False, 0, None, True),   # Empty idle scheduler is lazy-started.
        (False, 1, None, False),  # Work exists but dispatch loop is missing.
        (False, 0, False, False), # Dead supervisor even if queue has drained.
        (False, 1, True, True),
        (True, 0, None, False),
        (True, 1, True, False),
    ],
)
def test_scheduler_health_invariants(closed, pending, alive, expected):
    service = FakeService(closed=closed, pending=pending, alive=alive)
    assert is_scheduler_healthy(service) is expected


def test_http_probe_returns_503_for_dead_scheduler_but_liveness_stays_200(
    monkeypatch,
):
    monkeypatch.delenv("IFCFDS_API_KEY", raising=False)
    monkeypatch.setattr(
        server, "manager", FakeService(closed=False, pending=1, alive=False)
    )
    client = TestClient(server.app)
    assert client.get("/api/health").status_code == 200
    response = client.get("/api/scheduler-health")
    assert response.status_code == 503
    assert response.json()["detail"] == "Job scheduler unavailable"


def test_http_probe_returns_ok_for_idle_healthy_scheduler(monkeypatch):
    monkeypatch.delenv("IFCFDS_API_KEY", raising=False)
    monkeypatch.setattr(server, "manager", FakeService())
    response = TestClient(server.app).get("/api/scheduler-health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "component": "job_scheduler"}


def test_http_probe_uses_same_api_key_guard_as_other_api_routes(monkeypatch):
    monkeypatch.setenv("IFCFDS_API_KEY", "test-protected-scheduler-probe")
    monkeypatch.setattr(server, "manager", FakeService())
    client = TestClient(server.app)
    assert client.get("/api/scheduler-health").status_code == 401
    assert client.get(
        "/api/scheduler-health",
        headers={"x-api-key": "test-protected-scheduler-probe"},
    ).status_code == 200
