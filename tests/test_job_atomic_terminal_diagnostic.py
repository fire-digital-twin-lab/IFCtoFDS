"""Atomic terminal diagnostic publication under partial writes and races."""

import json
import os

import pytest

from ifc_to_fds.adapters.jobs.service import JobService


def _job(tmp_path):
    return {"id": "atomic-diagnostic", "directory": str(tmp_path)}


def _temporary_files(tmp_path):
    return list(tmp_path.glob(".diagnostics-*.tmp"))


def test_diagnostic_publish_is_complete_and_leaves_no_temporary(tmp_path):
    JobService._terminal_diagnostic(_job(tmp_path), "TimeoutError", "deadline")
    result = json.loads((tmp_path / "diagnostics.json").read_text(encoding="utf-8"))
    assert result["name"] == "TimeoutError"
    assert result["message"] == "deadline"
    assert result["jobId"] == "atomic-diagnostic"
    assert not _temporary_files(tmp_path)


def test_fsync_failure_never_publishes_partial_diagnostic(tmp_path, monkeypatch):
    def incomplete_flush(_fd):
        raise OSError("Simulated disk failure after buffered write")

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", incomplete_flush)
        with pytest.raises(OSError, match="Simulated disk failure"):
            JobService._terminal_diagnostic(_job(tmp_path), "TimeoutError", "deadline")

    assert not (tmp_path / "diagnostics.json").exists()
    assert not _temporary_files(tmp_path)
    # A later retry must publish the full original terminal reason.
    JobService._terminal_diagnostic(_job(tmp_path), "TimeoutError", "deadline")
    assert json.loads((tmp_path / "diagnostics.json").read_text())["name"] == "TimeoutError"


def test_link_failure_never_publishes_truncated_diagnostic(tmp_path, monkeypatch):
    def cannot_publish(_temporary, _target):
        raise PermissionError("Filesystem refuses atomic publication")

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", cannot_publish)
        with pytest.raises(PermissionError, match="Filesystem refuses"):
            JobService._terminal_diagnostic(_job(tmp_path), "ResourceExhaustedError", "rss")

    assert not (tmp_path / "diagnostics.json").exists()
    assert not _temporary_files(tmp_path)


def test_concurrent_worker_diagnostic_wins_no_clobber(tmp_path, monkeypatch):
    original = {"name": "WorkerError", "message": "richer worker report", "stack": "full"}
    path = tmp_path / "diagnostics.json"

    def concurrent_publish(_temporary, destination):
        assert destination == path
        path.write_text(json.dumps(original), encoding="utf-8")
        raise FileExistsError("Worker published its diagnostic first")

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", concurrent_publish)
        JobService._terminal_diagnostic(_job(tmp_path), "TimeoutError", "deadline")
    assert json.loads(path.read_text(encoding="utf-8")) == original
    assert not _temporary_files(tmp_path)
