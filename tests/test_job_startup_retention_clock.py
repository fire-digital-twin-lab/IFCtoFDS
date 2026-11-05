"""P1: startup retention must honor SQLite timestamps instead of directory mtime."""

import os
import time

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService


def _seed(root, jid, *, finished, last_accessed, state="COMPLETED", durable=False):
    directory = root / f"job-{jid}"
    directory.mkdir()
    artifact = directory / "result.json"
    artifact.write_text('{"fixture":true}', encoding="utf-8")
    now = time.time()
    JobRepository(root=root).register(
        jid,
        {
            "id": jid,
            "state": state,
            "directory": str(directory),
            "mode": "convert",
            "created": now - 7200,
            "started": now - 7000,
            "finished": finished,
            "last_accessed": last_accessed,
            "durable": durable,
            "retention_s": 60,
            "process": None,
        },
    )
    return directory, artifact


def test_restart_preserves_recently_accessed_artifact_despite_old_directory_mtime(
    tmp_path,
):
    now = time.time()
    directory, artifact = _seed(
        tmp_path, "recent-access", finished=now - 3600,
        last_accessed=now - 5,
    )
    os.utime(directory, (now - 4000, now - 4000))
    service = JobService(root=tmp_path, retention_s=60)
    try:
        assert directory.is_dir()
        assert artifact.is_file()
        assert JobRepository(root=tmp_path).get("recent-access") is not None
    finally:
        service.close()


def test_restart_expires_old_sqlite_access_even_when_directory_mtime_is_recent(
    tmp_path,
):
    now = time.time()
    directory, _ = _seed(
        tmp_path, "stale-access", finished=now - 3600,
        last_accessed=now - 3500,
    )
    os.utime(directory, (now, now))
    service = JobService(root=tmp_path, retention_s=60)
    try:
        assert not directory.exists()
        assert JobRepository(root=tmp_path).get("stale-access") is None
    finally:
        service.close()


def test_startup_does_not_delete_active_job_before_recovery(tmp_path):
    now = time.time()
    directory, _ = _seed(
        tmp_path, "crashed-worker", finished=None,
        last_accessed=now - 3600, state="RUNNING",
    )
    os.utime(directory, (now - 7000, now - 7000))
    service = JobService(root=tmp_path, retention_s=60)
    try:
        # Reconciliation may mark it FAILED, but the job directory and its
        # diagnostic must remain; active work is never purged by retention.
        assert directory.is_dir()
        assert (directory / "diagnostics.json").is_file()
        assert JobRepository(root=tmp_path).get("crashed-worker")["state"] == "FAILED"
    finally:
        service.close()


def test_durable_artifact_ignores_expired_retention_clock(tmp_path):
    now = time.time()
    directory, artifact = _seed(
        tmp_path, "durable-result", finished=now - 7200,
        last_accessed=now - 7100, durable=True,
    )
    os.utime(directory, (now - 7200, now - 7200))
    service = JobService(root=tmp_path, retention_s=60)
    try:
        assert directory.is_dir()
        assert artifact.is_file()
        assert JobRepository(root=tmp_path).get("durable-result") is not None
    finally:
        service.close()
