"""Regression: cancellation must survive failure writing diagnostic files."""

import logging
import time

import pytest

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService


@pytest.mark.parametrize("exc_type", [PermissionError, OSError])
def test_cancel_returns_durable_state_when_diagnostic_write_fails(
    tmp_path, monkeypatch, caplog, exc_type
):
    service = JobService(root=tmp_path)
    jid = "cancel-diagnostic-io"
    directory = tmp_path / f"job-{jid}"
    directory.mkdir()
    (directory / "source-test.ifc").write_bytes(b"IFC")
    (directory / "request.json").write_text("{}", encoding="utf-8")
    now = time.time()
    service.repository.register(
        jid,
        {
            "id": jid,
            "directory": str(directory),
            "mode": "convert",
            "state": "QUEUED",
            "created": now,
            "started": None,
            "finished": None,
            "last_accessed": now,
            "process": None,
            "durable": False,
        },
    )

    def denied_diagnostic(_job, _name, _message):
        raise exc_type("Diagnostic storage is unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(
            JobService, "_terminal_diagnostic", staticmethod(denied_diagnostic)
        )
        with caplog.at_level(logging.ERROR):
            cancelled = service.cancel(jid)

    try:
        assert cancelled["state"] == "CANCELLED"
        persisted = JobRepository(root=tmp_path).get(jid)
        assert persisted is not None
        assert persisted["state"] == "CANCELLED"
        assert not (directory / "source-test.ifc").exists()
        assert not (directory / "request.json").exists()
        assert "Could not write cancellation diagnostic" in caplog.text
        assert not (directory / "diagnostics.json").exists()
    finally:
        service.close()
