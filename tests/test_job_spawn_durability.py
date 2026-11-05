"""P1: never spawn a worker without durable RUNNING metadata."""

import sqlite3
import time

from ifc_to_fds.adapters.jobs.repository import JobPersistenceError, JobRepository
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
        raise sqlite3.DatabaseError("simulated disk full")


class FakeProcess:
    pid = None
    returncode = 0

    def poll(self):
        return self.returncode


def _seed(service, jid):
    directory = service.root / ("job-" + jid)
    directory.mkdir()
    source = directory / "source-0.ifc"
    source.write_text("must survive storage failure", encoding="utf-8")
    now = time.time()
    service.repository.register(
        jid,
        {
            "id": jid,
            "state": "QUEUED",
            "mode": "inventory",
            "directory": str(directory),
            "created": now,
            "started": None,
            "finished": None,
            "last_accessed": now,
            "process": None,
        },
    )
    return source


def _step(service):
    service.closed = False
    service.wake = SingleTurnWake(service)
    service._loop()


def test_no_subprocess_is_created_until_running_state_commits(tmp_path, monkeypatch):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "spawn-sqlite-unavailable"
    source = _seed(service, jid)
    called = []

    def start_worker(*_args, **_kwargs):
        called.append(True)
        return FakeProcess()

    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "_get_connection", BrokenUpdateConnection)
        patch.setattr(
            "ifc_to_fds.adapters.jobs.service.subprocess.Popen", start_worker
        )
        _step(service)

    assert not called, "never spawn a worker with uncommitted metadata"
    assert service.repository.get(jid)["state"] == "QUEUED"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "QUEUED"
    assert source.exists()

    with monkeypatch.context() as patch:
        patch.setattr(
            "ifc_to_fds.adapters.jobs.service.subprocess.Popen", start_worker
        )
        _step(service)

    assert called == [True]
    assert service.repository.get(jid)["state"] == "RUNNING"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
    assert service.repository.get(jid)["process"] is not None
    assert source.exists()
    service.close()


def test_spawn_oserror_commits_failed_before_cleanup(tmp_path, monkeypatch):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "spawn-exec-error"
    source = _seed(service, jid)

    def fail_spawn(*_args, **_kwargs):
        raise OSError("worker executable unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(
            "ifc_to_fds.adapters.jobs.service.subprocess.Popen", fail_spawn
        )
        _step(service)

    state = service.repository.get(jid)
    disk = JobRepository(root=tmp_path).get(jid)
    assert state["state"] == disk["state"] == "FAILED"
    assert "worker executable unavailable" in disk["error"]
    assert not source.exists()
    assert (source.parent / "diagnostics.json").exists()
    service.close()


def test_spawn_error_survives_sqlite_failure_then_retries_original_reason(
    tmp_path, monkeypatch
):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "spawn-terminal-disk-full"
    source = _seed(service, jid)
    original_set_durable = service.repository.set_durable

    def fail_only_failed(job_id, job):
        if job["state"] == "FAILED":
            raise JobPersistenceError("simulated disk full after spawn error")
        return original_set_durable(job_id, job)

    def fail_spawn(*_args, **_kwargs):
        raise OSError("spawn denied")

    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "set_durable", fail_only_failed)
        patch.setattr(
            "ifc_to_fds.adapters.jobs.service.subprocess.Popen", fail_spawn
        )
        _step(service)

    assert service.repository.get(jid)["state"] == "RUNNING"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
    assert source.exists()
    assert jid in service._pending_terminal

    # Once SQLite recovers, the original reason is finalized without a new
    # process launch or a bogus missing-handle overwrite.
    with monkeypatch.context() as patch:
        patch.setattr(
            "ifc_to_fds.adapters.jobs.service.subprocess.Popen",
            lambda *_a, **_k: (_ for _ in ()).throw(
                AssertionError("must not retry spawning the worker")
            ),
        )
        _step(service)

    disk = JobRepository(root=tmp_path).get(jid)
    assert disk["state"] == service.repository.get(jid)["state"] == "FAILED"
    assert "spawn denied" in disk["error"]
    assert jid not in service._pending_terminal
    assert not source.exists()
    service.close()
