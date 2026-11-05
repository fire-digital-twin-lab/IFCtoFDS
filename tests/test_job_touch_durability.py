"""P1 regression: read-only API access must not silently lose retention updates."""

import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from ifc_to_fds import server
from ifc_to_fds.adapters.jobs.repository import JobPersistenceError, JobRepository
from ifc_to_fds.adapters.jobs.service import JobService


class BrokenUpdateConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, *_params):
        assert "UPDATE jobs SET" in statement
        raise sqlite3.DatabaseError("simulated disk full")


def _finished_job(service, jid):
    directory = service.root / ("job-" + jid)
    directory.mkdir()
    (directory / "diagnostics.json").write_text("{}", encoding="utf-8")
    now = time.time()
    job = {
        "id": jid,
        "state": "COMPLETED",
        "mode": "inventory",
        "directory": str(directory),
        "created": now - 120,
        "started": now - 100,
        "finished": now - 90,
        "last_accessed": now - 70,
        "process": None,
    }
    service.repository.register(jid, job)
    return job["last_accessed"]


def test_touch_does_not_publish_access_time_when_sqlite_commit_fails(
    tmp_path, monkeypatch
):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "read-retention-disk-full"
    previous = _finished_job(service, jid)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(service.repository, "_get_connection", BrokenUpdateConnection)
            with pytest.raises(JobPersistenceError):
                service.touch(jid)

        assert service.repository.get(jid)["last_accessed"] == previous
        assert JobRepository(root=tmp_path).get(jid)["last_accessed"] == previous

        service.touch(jid)
        current = service.repository.get(jid)["last_accessed"]
        assert current > previous
        assert JobRepository(root=tmp_path).get(jid)["last_accessed"] == current
    finally:
        service.close()


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/jobs/{jid}/result",
        "/api/jobs/{jid}/diagnostics",
    ],
)
def test_download_routes_return_503_when_access_timestamp_is_not_durable(
    tmp_path, monkeypatch, endpoint
):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "read-http-disk-full"
    previous = _finished_job(service, jid)
    monkeypatch.delenv("IFCFDS_API_KEY", raising=False)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(server, "manager", service)
            patch.setattr(service.repository, "_get_connection", BrokenUpdateConnection)
            response = TestClient(server.app).get(endpoint.format(jid=jid))

        assert response.status_code == 503
        assert response.json() == {
            "detail": "Job metadata storage unavailable; retry later"
        }
        assert service.repository.get(jid)["last_accessed"] == previous
        assert JobRepository(root=tmp_path).get(jid)["last_accessed"] == previous
    finally:
        service.close()
