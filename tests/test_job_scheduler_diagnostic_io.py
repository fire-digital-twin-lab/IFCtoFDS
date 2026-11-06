"""Scheduler must recover from diagnostic I/O failures without false verdicts."""

import logging
import time

import pytest

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService


class TwoTurnWake:
    """Drive the wrapper retry and next successful scheduler pass."""

    def __init__(self, service):
        self.service = service
        self.calls = 0

    def clear(self):
        pass

    def set(self):
        pass

    def wait(self, _timeout):
        self.calls += 1
        if self.calls >= 2:
            self.service.closed = True


class FinishedProcess:
    pid = None
    returncode = 0

    def poll(self):
        return 0


@pytest.mark.parametrize(
    ("scenario", "original_state", "expected_state"),
    [
        ("expired_queue", "QUEUED", "TIMED_OUT"),
        ("missing_worker", "RUNNING", "FAILED"),
        ("invalid_result", "RUNNING", "FAILED"),
    ],
)
def test_diagnostic_write_failure_preserves_sqlite_until_recovery(
    tmp_path, monkeypatch, caplog, scenario, original_state, expected_state
):
    service = JobService(root=tmp_path, retention_s=3600, queue_timeout_s=1)
    jid = "diagnostic-io-" + scenario
    directory = tmp_path / ("job-" + jid)
    directory.mkdir()
    source = directory / "source-model.ifc"
    source.write_bytes(b"IFC")
    now = time.time()
    if scenario == "invalid_result":
        (directory / "result.json").write_text("{invalid", encoding="utf-8")
    service.repository.register(
        jid,
        {
            "id": jid,
            "state": original_state,
            "directory": str(directory),
            "mode": "convert",
            "created": now - 120 if scenario == "expired_queue" else now,
            "started": now if original_state == "RUNNING" else None,
            "finished": None,
            "last_accessed": now,
            "process": FinishedProcess() if scenario == "invalid_result" else None,
            "durable": False,
        },
    )
    real_diagnostic = JobService._terminal_diagnostic
    attempts = []

    def intermittent_diagnostic(job, name, message):
        attempts.append(name)
        if len(attempts) == 1:
            # No SQLite transition or file cleanup may precede the retry.
            assert service.repository.get(jid)["state"] == original_state
            assert JobRepository(root=tmp_path).get(jid)["state"] == original_state
            assert source.is_file()
            raise PermissionError("Diagnostic directory is temporarily locked")
        return real_diagnostic(job, name, message)

    wake = TwoTurnWake(service)
    service.wake = wake
    try:
        with monkeypatch.context() as patch:
            patch.setattr(
                JobService, "_terminal_diagnostic",
                staticmethod(intermittent_diagnostic),
            )
            with caplog.at_level(logging.ERROR):
                service._loop()
        assert len(attempts) == 2
        assert wake.calls == 2
        assert "Scheduler I/O failure" in caplog.text
        assert service.repository.get(jid)["state"] == expected_state
        assert JobRepository(root=tmp_path).get(jid)["state"] == expected_state
        assert (directory / "diagnostics.json").is_file()
        assert not source.exists()
    finally:
        service.close()
