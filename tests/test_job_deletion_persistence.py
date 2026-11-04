"""Regression tests: SQLite deletion must commit before purging job evidence."""

import os
import shutil
import sqlite3
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from ifc_to_fds.adapters.jobs.repository import JobPersistenceError, JobRepository
from ifc_to_fds.adapters.jobs.service import JobService
from ifc_to_fds.server import app, manager


class BrokenDeleteConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, *args):
        assert "DELETE FROM jobs" in sql
        raise sqlite3.OperationalError("disk full")


def _terminal_job(jid, directory):
    return {
        "id": jid, "state": "COMPLETED",
        "directory": str(directory), "mode": "inventory",
        "created": time.time() - 300, "finished": time.time() - 200,
    }


def test_failed_sqlite_delete_keeps_cache_and_durable_row(tmp_path, monkeypatch):
    repo = JobRepository(root=tmp_path)
    directory = tmp_path / "job-one"
    directory.mkdir()
    (directory / "result.json").write_text("{}", encoding="utf-8")
    repo.register("job-one", _terminal_job("job-one", directory))
    monkeypatch.setattr(repo, "_get_connection", BrokenDeleteConnection)

    with pytest.raises(JobPersistenceError, match="Could not delete"):
        repo.delete("job-one")

    assert repo.get("job-one") is not None
    assert JobRepository(root=tmp_path).get("job-one") is not None
    assert directory.joinpath("result.json").is_file()


def test_api_purge_returns_503_without_deleting_artifacts(tmp_path, monkeypatch):
    jid = "test-delete-failure-" + uuid.uuid4().hex
    directory = manager.root / ("job-" + jid)
    directory.mkdir(parents=True)
    (directory / "evidence.txt").write_text("keep", encoding="utf-8")
    manager.repository.set(jid, _terminal_job(jid, directory))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(manager.repository, "_get_connection", BrokenDeleteConnection)
            response = TestClient(app).delete(
                f"/api/jobs/{jid}", params={"purge": "true"}
            )
        assert response.status_code == 503, response.text
        assert manager.repository.get(jid) is not None
        assert (directory / "evidence.txt").read_text(encoding="utf-8") == "keep"
    finally:
        manager.repository.delete(jid)
        shutil.rmtree(directory, ignore_errors=True)


def test_startup_retention_does_not_purge_artifacts_on_sqlite_failure(
    tmp_path, monkeypatch
):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "job-expired"
    directory = tmp_path / jid
    directory.mkdir()
    (directory / "evidence.txt").write_text("keep", encoding="utf-8")
    service.repository.register(jid, _terminal_job(jid, directory))
    old = time.time() - 7200
    os.utime(directory, (old, old))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(service.repository, "_get_connection", BrokenDeleteConnection)
            service.cleanup_orphaned_directories(max_age_s=1)
        assert service.repository.get(jid) is not None
        assert (directory / "evidence.txt").read_text(encoding="utf-8") == "keep"
        assert JobRepository(root=tmp_path).get(jid) is not None
    finally:
        service.close()
