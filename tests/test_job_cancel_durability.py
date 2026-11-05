"""P1 regression: cancellation must commit to SQLite before publishing state."""

import shutil
import sqlite3
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from ifc_to_fds.adapters.jobs.repository import JobPersistenceError, JobRepository
from ifc_to_fds.adapters.jobs.service import JobService
from ifc_to_fds.server import app, manager


def _queued(jid, directory):
    now = time.time()
    return {
        "id": jid, "state": "QUEUED", "mode": "inventory",
        "directory": str(directory), "created": now,
        "started": None, "finished": None, "last_accessed": now,
    }


class BrokenUpdateConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, *_args):
        assert "UPDATE jobs SET" in sql
        raise sqlite3.DatabaseError("disk full")


def test_failed_cancel_keeps_original_memory_sqlite_and_source(tmp_path, monkeypatch):
    service = JobService(root=tmp_path)
    jid = "cancel-fails"
    directory = tmp_path / ("job-" + jid)
    directory.mkdir()
    source = directory / "source-original.ifc"
    source.write_text("retain source", encoding="utf-8")
    service.repository.register(jid, _queued(jid, directory))
    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "_get_connection", BrokenUpdateConnection)
        with pytest.raises(JobPersistenceError, match="Could not update"):
            service.cancel(jid)
    assert service.repository.get(jid)["state"] == "QUEUED"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "QUEUED"
    assert source.exists()
    assert not (directory / "diagnostics.json").exists()
    service.closed = True


def test_successful_cancel_is_durable_and_has_diagnostic(tmp_path):
    service = JobService(root=tmp_path)
    jid = "cancel-success"
    directory = tmp_path / ("job-" + jid)
    directory.mkdir()
    service.repository.register(jid, _queued(jid, directory))
    result = service.cancel(jid)
    assert result["state"] == "CANCELLED"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "CANCELLED"
    assert (directory / "diagnostics.json").exists()
    service.close()


def test_cancel_http_returns_503_on_disk_error_and_preserves_queued(tmp_path, monkeypatch):
    jid = "test-cancel-" + uuid.uuid4().hex
    directory = manager.root / ("job-" + jid)
    directory.mkdir(parents=True)
    manager.repository.register(jid, _queued(jid, directory))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(manager.repository, "_get_connection", BrokenUpdateConnection)
            response = TestClient(app).post(f"/api/jobs/{jid}/cancel")
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "Job metadata storage unavailable; retry later"
        assert manager.repository.get(jid)["state"] == "QUEUED"
        assert JobRepository(root=manager.root).get(jid)["state"] == "QUEUED"
    finally:
        # The scheduler can write diagnostics/error.txt between the HTTP
        # assertion and test teardown. Remove the fixture under its lock,
        # without weakening the QUEUED/SQLite assertions above.
        with manager.lock:
            manager.repository.delete(jid)
            shutil.rmtree(directory)
