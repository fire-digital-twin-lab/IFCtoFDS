"""Terminal input cleanup must not crash the scheduler on filesystem errors."""

import logging
import time
from pathlib import Path

import pytest

from ifc_to_fds.adapters.jobs.service import JobService


@pytest.mark.parametrize("blocked_name", ["source-0.ifc", "request.json"])
def test_cleanup_keeps_scheduler_safe_when_file_unlink_is_denied(
    tmp_path, monkeypatch, caplog, blocked_name
):
    directory = tmp_path / "job-file-locked"
    directory.mkdir()
    source = directory / "source-0.ifc"
    request = directory / "request.json"
    source.write_bytes(b"IFC")
    request.write_text("{}", encoding="utf-8")
    original_unlink = Path.unlink

    def locked_unlink(path, *args, **kwargs):
        if path.name == blocked_name:
            raise PermissionError("File in use")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_unlink)
    with caplog.at_level(logging.ERROR):
        JobService._cleanup({"id": "locked", "directory": str(directory)})

    assert (directory / blocked_name).exists()
    assert not (directory / (
        "request.json" if blocked_name == "source-0.ifc" else "source-0.ifc"
    )).exists()
    assert "Cannot delete terminal input" in caplog.text
    assert "locked" in caplog.text


def test_cancel_commits_terminal_state_even_if_input_cleanup_is_denied(
    tmp_path, monkeypatch, caplog
):
    service = JobService(root=tmp_path)
    directory = tmp_path / "job-locked-cancel"
    directory.mkdir()
    source = directory / "source-0.ifc"
    source.write_bytes(b"IFC")
    (directory / "request.json").write_text("{}", encoding="utf-8")
    now = time.time()
    service.repository.register(
        "locked-cancel",
        {
            "id": "locked-cancel",
            "directory": str(directory),
            "mode": "convert",
            "state": "QUEUED",
            "created": now,
            "started": None,
            "last_accessed": now,
            "finished": None,
            "process": None,
            "durable": False,
        },
    )
    original_unlink = Path.unlink

    def locked_unlink(path, *args, **kwargs):
        if path == source:
            raise PermissionError("Source file held by antivirus")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_unlink)
    try:
        with caplog.at_level(logging.ERROR):
            result = service.cancel("locked-cancel")
        assert result["state"] == "CANCELLED"
        assert service.repository.get("locked-cancel")["state"] == "CANCELLED"
        assert source.exists()
        assert "Cannot delete terminal input" in caplog.text
    finally:
        service.close()
