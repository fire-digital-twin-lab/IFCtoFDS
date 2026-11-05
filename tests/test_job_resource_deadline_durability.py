"""Regression: deadline/RSS terminal transitions are durable before input cleanup."""

import sqlite3
import time

import pytest

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService


class BrokenConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, *_params):
        assert "UPDATE jobs SET" in sql
        raise sqlite3.DatabaseError("disk full")


class SingleTurnWake:
    def __init__(self, service):
        self.service = service

    def clear(self):
        pass

    def set(self):
        pass

    def wait(self, _timeout):
        self.service.closed = True


class LiveProcess:
    pid = 12345
    returncode = None

    def poll(self):
        # A real child has exited after _stop(), which must not overwrite the
        # original resource/deadline reason when SQLite recovers.
        return self.returncode


class HighMemoryProcess:
    def __init__(self, _pid):
        pass

    def memory_info(self):
        class Info:
            rss = 50 * 1024 * 1024
        return Info()

    def children(self, recursive=True):
        assert recursive
        return []


def _seed(service, jid, *, started):
    directory = service.root / ("job-" + jid)
    directory.mkdir()
    source = directory / "source-model.ifc"
    source.write_text("retain after failed commit", encoding="utf-8")
    now = time.time()
    service.repository.register(
        jid,
        {
            "id": jid,
            "state": "RUNNING",
            "mode": "inventory",
            "directory": str(directory),
            "created": now - 120,
            "started": started,
            "finished": None,
            "last_accessed": now,
            "process": LiveProcess(),
        },
    )
    return source


def _step(service):
    service.closed = False
    service.wake = SingleTurnWake(service)
    service._loop()


@pytest.mark.parametrize("failure", ["deadline", "memory"])
def test_worker_limit_failure_preserves_source_until_sqlite_commits(
    tmp_path, monkeypatch, failure
):
    service = JobService(root=tmp_path, timeout_s=1 if failure == "deadline" else 1800,
                         max_memory_mb=10, retention_s=3600)
    jid = "worker-limit-" + failure
    started = time.time() - 120 if failure == "deadline" else time.time()
    source = _seed(service, jid, started=started)
    stopped = []
    def stop_process(process):
        stopped.append(process)
        process.returncode = -9

    monkeypatch.setattr(service, "_stop", stop_process)

    if failure == "memory":
        monkeypatch.setattr(
            "ifc_to_fds.adapters.jobs.service.psutil.Process", HighMemoryProcess
        )
    else:
        # Avoid RSS path: verify the deadline path specifically.
        service.repository.get(jid)["process"].pid = None

    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "_get_connection", BrokenConnection)
        _step(service)

    assert stopped, "the worker must be stopped after exceeding the resource limit"
    assert service.repository.get(jid)["state"] == "RUNNING"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
    assert source.read_text(encoding="utf-8") == "retain after failed commit"

    # The child is now exited (poll() == -9), but a repeated SQLite outage
    # still must not publish FAILED with generic "Worker exited -9".
    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "_get_connection", BrokenConnection)
        _step(service)
    assert service.repository.get(jid)["state"] == "RUNNING"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
    assert source.exists()
    assert len(stopped) == 1

    _step(service)
    expected = "TIMED_OUT" if failure == "deadline" else "FAILED"
    assert service.repository.get(jid)["state"] == expected
    durable = JobRepository(root=tmp_path).get(jid)
    assert durable["state"] == expected
    assert service.repository.get(jid)["error"] == durable["error"]
    if failure == "deadline":
        assert durable["error"] == "Job deadline exceeded"
    else:
        assert durable["error"].startswith("RESOURCE_EXHAUSTED:")
    assert len(stopped) == 1
    assert not source.exists()
    assert (source.parent / "diagnostics.json").is_file()
    service.close()
