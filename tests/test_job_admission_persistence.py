"""Hồi quy: không tiếp nhận công việc nếu SQLite không lưu được metadata."""

import logging
import sqlite3

import pytest
from fastapi.testclient import TestClient

from ifc_to_fds.adapters.jobs.repository import JobPersistenceError, JobRepository
from ifc_to_fds.adapters.jobs.service import JobService
from ifc_to_fds.server import app, manager


def _job(directory):
    return {
        "id": "job-admission",
        "state": "QUEUED",
        "directory": str(directory),
        "mode": "convert",
        "created": 123.0,
    }


def test_registration_sqlite_failure_does_not_publish_ghost_job(
    tmp_path, monkeypatch, caplog
):
    repo = JobRepository(root=tmp_path)

    class BrokenConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, *args, **kwargs):
            raise sqlite3.DatabaseError("disk full")

    monkeypatch.setattr(repo, "_get_connection", lambda: BrokenConnection())
    with caplog.at_level(logging.ERROR):
        with pytest.raises(JobPersistenceError, match="Could not persist"):
            repo.register("job-admission", _job(tmp_path / "job-admission"))
    assert "Failed to persist job job-admission" in caplog.text
    assert repo.get("job-admission") is None
    assert JobRepository(root=tmp_path).get("job-admission") is None


def test_successful_registration_publishes_only_after_database_commit(
    tmp_path, monkeypatch
):
    repo = JobRepository(root=tmp_path)
    persist = repo._persist_job

    def persist_before_visibility(jid, job, *, require_durable=False):
        assert repo.get(jid) is None
        assert require_durable is True
        return persist(jid, job, require_durable=require_durable)

    monkeypatch.setattr(repo, "_persist_job", persist_before_visibility)
    repo.register("job-admission", _job(tmp_path / "job-admission"))
    assert repo.get("job-admission")["state"] == "QUEUED"
    assert JobRepository(root=tmp_path).get("job-admission")["state"] == "QUEUED"


def test_cross_instance_duplicate_registration_never_overwrites_sqlite(tmp_path):
    """Two independent repository caches must not bypass SQLite uniqueness."""
    first = JobRepository(root=tmp_path)
    second = JobRepository(root=tmp_path)
    original = _job(tmp_path / "original")
    first.register("job-admission", original)

    conflicting = _job(tmp_path / "different")
    conflicting["state"] = "RUNNING"
    with pytest.raises(JobPersistenceError, match="already registered"):
        second.register("job-admission", conflicting)

    assert second.get("job-admission") is None
    persisted = JobRepository(root=tmp_path).get("job-admission")
    assert persisted["state"] == "QUEUED"
    assert persisted["directory"] == str(tmp_path / "original")


def test_service_does_not_spawn_worker_after_registration_failure(
    tmp_path, monkeypatch
):
    service = JobService(root=tmp_path)
    directory = tmp_path / "job-admission"
    directory.mkdir()
    before = service.repository.count_pending()

    def reject(*args, **kwargs):
        raise JobPersistenceError("failed registration")

    monkeypatch.setattr(service.repository, "register", reject)
    with pytest.raises(JobPersistenceError, match="failed registration"):
        service.submit([], {}, directory, mode="convert")
    assert service.repository.count_pending() == before
    assert service.thread is None
    assert not service.wake.is_set()
    service.close()


@pytest.mark.parametrize(
    "endpoint,file_field",
    [
        ("/api/jobs", "files"),
        ("/api/preview-jobs", "file"),
        ("/api/inventory", "file"),
    ],
)
def test_http_admission_returns_503_and_cleans_uploaded_directory(
    tiny_ifc, monkeypatch, endpoint, file_field
):
    path, _, _ = tiny_ifc
    existing = {p.name for p in manager.root.glob("job-*")}
    client = TestClient(app)
    # These tests exercise the same fail-closed boundary with an in-memory
    # fake persistence error. No worker should be started and no uploaded
    # IFC source should remain available after the rejected request.
    with monkeypatch.context() as patch:
        patch.setattr(manager, "can_accept", lambda: True)
        patch.setattr(
            manager.repository,
            "register",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                JobPersistenceError("simulated disk error")
            ),
        )
        response = client.post(
            endpoint,
            files={file_field: ("tiny.ifc", path.read_bytes())},
        )
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Job metadata storage unavailable; retry later"
    assert {p.name for p in manager.root.glob("job-*")} == existing
