"""Stopped worker diagnostic outages must not overwrite terminal reason.

Production invariant: a worker already killed for deadline or memory must not
later become generic "Worker exited -9" while diagnostic/SQLite I/O is failing.
"""

import json
import sqlite3
import time

import pytest

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService


class OnePassWake:
    def __init__(self, service):
        self.service = service

    def clear(self):
        pass

    def set(self):
        pass

    def wait(self, _timeout):
        self.service.closed = True


class KilledWorker:
    def __init__(self, *, pid):
        self.pid = pid
        self.returncode = None

    def poll(self):
        return self.returncode


class HighMemory:
    def __init__(self, _pid):
        pass

    def memory_info(self):
        class Memory:
            rss = 64 * 1024 * 1024
        return Memory()

    def children(self, recursive=True):
        assert recursive
        return []


class DiskFullConnection:
    def __enter__(self):
        return self

    def __exit__(self, _exception_type, _exception, _traceback):
        return False

    def execute(self, sql, *_args):
        assert "UPDATE jobs SET" in sql
        raise sqlite3.DatabaseError("SQLite disk full")


def one_scheduler_turn(service):
    service.closed = False
    service.wake = OnePassWake(service)
    service._loop()


@pytest.mark.parametrize("cause", ["memory", "deadline"])
@pytest.mark.parametrize("sqlite_fails_after_recovery", [False, True])
def test_original_terminal_reason_survives_diagnostic_and_sqlite_failures(
    tmp_path, monkeypatch, cause, sqlite_fails_after_recovery
):
    service = JobService(
        root=tmp_path,
        retention_s=3600,
        timeout_s=1 if cause == "deadline" else 1800,
        max_memory_mb=10,
    )
    jid = "stopped-diagnostic-" + cause
    directory = tmp_path / ("job-" + jid)
    directory.mkdir()
    source = directory / "source-test.ifc"
    source.write_bytes(b"IFC")
    worker = KilledWorker(pid=1234 if cause == "memory" else None)
    now = time.time()
    service.repository.register(
        jid,
        {
            "id": jid,
            "state": "RUNNING",
            "directory": str(directory),
            "mode": "inventory",
            "created": now - 120,
            "started": now - 120 if cause == "deadline" else now,
            "finished": None,
            "last_accessed": now,
            "process": worker,
            "durable": False,
        },
    )
    stopped = []

    def stop_worker(process):
        stopped.append(process)
        process.returncode = -9

    original_diagnostic = service._terminal_diagnostic
    allow_diagnostic = {"value": False}
    diagnostic_calls = []

    def unreliable_diagnostic(job, name, message):
        diagnostic_calls.append(name)
        if not allow_diagnostic["value"]:
            raise PermissionError("diagnostic output locked")
        return original_diagnostic(job, name, message)

    monkeypatch.setattr(service, "_stop", stop_worker)
    monkeypatch.setattr(service, "_terminal_diagnostic", unreliable_diagnostic)
    if cause == "memory":
        monkeypatch.setattr(
            "ifc_to_fds.adapters.jobs.service.psutil.Process", HighMemory
        )
    try:
        one_scheduler_turn(service)
        assert len(stopped) == 1
        assert service.repository.get(jid)["state"] == "RUNNING"
        assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
        assert source.is_file()
        assert not (directory / "diagnostics.json").exists()
        assert jid in service._pending_terminal
        assert jid in service._pending_diagnostic

        # Re-attempt the diagnostic before ANY durable terminal transition.
        allow_diagnostic["value"] = True
        if sqlite_fails_after_recovery:
            with monkeypatch.context() as patch:
                patch.setattr(service.repository, "_get_connection", DiskFullConnection)
                one_scheduler_turn(service)
            assert service.repository.get(jid)["state"] == "RUNNING"
            assert JobRepository(root=tmp_path).get(jid)["state"] == "RUNNING"
            assert source.is_file()
            assert jid in service._pending_terminal
            assert jid not in service._pending_diagnostic

        one_scheduler_turn(service)
        expected = "FAILED" if cause == "memory" else "TIMED_OUT"
        durable = JobRepository(root=tmp_path).get(jid)
        assert durable["state"] == expected
        assert service.repository.get(jid)["state"] == expected
        assert len(stopped) == 1
        assert "Worker exited" not in durable["error"]
        if cause == "memory":
            assert durable["error"].startswith("RESOURCE_EXHAUSTED:")
            assert diagnostic_calls[-1] == "ResourceExhaustedError"
        else:
            assert durable["error"] == "Job deadline exceeded"
            assert diagnostic_calls[-1] == "TimeoutError"
        diagnostic = json.loads((directory / "diagnostics.json").read_text(encoding="utf-8"))
        assert diagnostic["name"] == diagnostic_calls[-1]
        assert not source.exists()
        assert jid not in service._pending_terminal
        assert jid not in service._pending_diagnostic
    finally:
        service.close()
