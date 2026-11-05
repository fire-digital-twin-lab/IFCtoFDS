"""P1: crash reconciliation and scheduler timeout must commit before cleanup."""

import sqlite3
import time

from ifc_to_fds.adapters.jobs.repository import (
    JobPersistenceError,
    JobRepository,
)
from ifc_to_fds.adapters.jobs.service import JobService


class SingleTurnWake:
    def __init__(self, service):
        self.service = service

    def clear(self):
        pass

    def set(self):
        pass

    def wait(self, _timeout):
        self.service.closed = True


class BrokenUpdateConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, *_args):
        assert "UPDATE jobs SET" in sql
        raise sqlite3.DatabaseError("disk full")


def _seed(repo, root, jid, state, *, age=0):
    directory = root / ("job-" + jid)
    directory.mkdir()
    source = directory / "source-model.ifc"
    source.write_text("must survive an uncommitted transition", encoding="utf-8")
    now = time.time()
    repo.register(
        jid,
        {
            "id": jid,
            "state": state,
            "mode": "inventory",
            "directory": str(directory),
            "created": now - age,
            "started": now if state == "RUNNING" else None,
            "finished": None,
            "last_accessed": now,
            "process": None,
        },
    )
    return source


def _one_turn(service):
    service.closed = False
    service.wake = SingleTurnWake(service)
    service._loop()


def test_queue_timeout_preserves_source_and_avoids_dispatch_on_db_failure(
    tmp_path, monkeypatch
):
    service = JobService(root=tmp_path, queue_timeout_s=1, retention_s=3600)
    jid = "queue-timeout-disk-full"
    source = _seed(service.repository, tmp_path, jid, "QUEUED", age=120)
    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "_get_connection", BrokenUpdateConnection)
        patch.setattr(
            "ifc_to_fds.adapters.jobs.service.subprocess.Popen",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("Expired job must not be dispatched while DB is down")
            ),
        )
        _one_turn(service)

    assert service.repository.get(jid)["state"] == "QUEUED"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "QUEUED"
    assert source.exists()

    _one_turn(service)
    assert service.repository.get(jid)["state"] == "TIMED_OUT"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "TIMED_OUT"
    assert not source.exists()
    service.close()


def test_missing_worker_preserves_source_until_terminal_commit(tmp_path, monkeypatch):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "missing-worker-disk-full"
    source = _seed(service.repository, tmp_path, jid, "RUNNING")
    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "_get_connection", BrokenUpdateConnection)
        _one_turn(service)

    assert service.repository.get(jid)["state"] == "RUNNING"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
    assert source.exists()

    _one_turn(service)
    assert service.repository.get(jid)["state"] == "FAILED"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "FAILED"
    assert not source.exists()
    service.close()


def test_startup_reconcile_never_deletes_source_when_sqlite_unavailable(
    tmp_path, monkeypatch
):
    jid = "restart-disk-full"
    repo = JobRepository(root=tmp_path)
    source = _seed(repo, tmp_path, jid, "RUNNING")

    def fail_commit(self, job_id, job):
        raise JobPersistenceError("simulated storage failure")

    with monkeypatch.context() as patch:
        patch.setattr(JobRepository, "set_durable", fail_commit)
        service = JobService(root=tmp_path, retention_s=3600)

    assert service.repository.get(jid)["state"] == "RUNNING"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
    assert source.exists()

    service._reconcile_startup_jobs()
    assert service.repository.get(jid)["state"] == "FAILED"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "FAILED"
    assert not source.exists()
    service.close()
