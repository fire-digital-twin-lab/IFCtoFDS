"""P1 regression: terminal worker state must be durable before source cleanup."""

import sqlite3
import time

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService


class FinishedProcess:
    pid = None
    returncode = 3

    def poll(self):
        return self.returncode


class SingleTurnWake:
    def __init__(self, service):
        self.service = service

    def clear(self):
        pass

    def set(self):
        pass

    def wait(self, _timeout):
        self.service.closed = True


class BrokenConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, *_args):
        assert "UPDATE jobs SET" in sql
        raise sqlite3.DatabaseError("disk full")


def test_terminal_update_failure_keeps_source_and_can_retry(tmp_path, monkeypatch):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "terminal-write-fails"
    directory = tmp_path / ("job-" + jid)
    directory.mkdir()
    source = directory / "source-model.ifc"
    source.write_text("original source", encoding="utf-8")
    now = time.time()
    service.repository.register(
        jid,
        {
            "id": jid,
            "state": "RUNNING",
            "mode": "inventory",
            "directory": str(directory),
            "created": now,
            "started": now,
            "finished": None,
            "last_accessed": now,
            "process": FinishedProcess(),
        },
    )

    # Deterministic scheduler iteration, without timing-dependent background threads.
    service.wake = SingleTurnWake(service)
    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "_get_connection", BrokenConnection)
        service._loop()

    assert service.repository.get(jid)["state"] == "RUNNING"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
    assert source.read_text(encoding="utf-8") == "original source"

    # SQLite recovered: the same finished worker is finalized and source cleanup
    # follows the successful committed state transition.
    service.closed = False
    service.wake = SingleTurnWake(service)
    service._loop()
    assert service.repository.get(jid)["state"] == "FAILED"
    assert JobRepository(root=tmp_path).get(jid)["state"] == "FAILED"
    assert not source.exists()
    service.close()
