"""P1: one local production scheduler must own each writable job root."""

import pytest

from ifc_to_fds.adapters.jobs.exclusive_lock import (
    ExclusiveJobRootLock,
    JobRootInUseError,
)
from ifc_to_fds.adapters.jobs.service import JobService


def test_exclusive_job_root_lock_rejects_second_holder(tmp_path):
    first = ExclusiveJobRootLock(tmp_path)
    lock_file = tmp_path / ".scheduler.lock"
    assert lock_file.is_file()
    try:
        with pytest.raises(JobRootInUseError, match="exclusive scheduler lock"):
            ExclusiveJobRootLock(tmp_path)
    finally:
        first.release()

    # The file remains, but the OS lock is released and can be reacquired.
    assert lock_file.is_file()
    another = ExclusiveJobRootLock(tmp_path)
    another.release()
    another.release()


@pytest.mark.parametrize("mode", ["staging", "production"])
def test_network_mode_refuses_second_job_service_on_same_root(
    tmp_path, monkeypatch, mode
):
    monkeypatch.setenv("IFCFDS_ENV", mode)
    first = JobService(root=tmp_path, retention_s=3600)
    try:
        with pytest.raises(JobRootInUseError):
            JobService(root=tmp_path, retention_s=3600)
    finally:
        first.close()

    second = JobService(root=tmp_path, retention_s=3600)
    second.close()


def test_local_mode_remains_compatible_with_independent_test_instances(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("IFCFDS_ENV", "local")
    first = JobService(root=tmp_path, retention_s=3600)
    second = JobService(root=tmp_path, retention_s=3600)
    try:
        assert first._root_lock is None
        assert second._root_lock is None
    finally:
        second.close()
        first.close()


def test_sqlite_initialization_failure_releases_process_lock(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("IFCFDS_ENV", "production")

    def failing_repository(*_args, **_kwargs):
        raise RuntimeError("injected SQLite initialization failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            "ifc_to_fds.adapters.jobs.service.JobRepository", failing_repository
        )
        with pytest.raises(RuntimeError, match="SQLite initialization failure"):
            JobService(root=tmp_path, retention_s=3600)

    lock = ExclusiveJobRootLock(tmp_path)
    lock.release()
