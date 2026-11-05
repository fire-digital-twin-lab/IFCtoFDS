"""WAL commit sync mode must match the deployment durability promise."""

import pytest

from ifc_to_fds.adapters.jobs.repository import JobRepository


@pytest.mark.parametrize(
    "environment,expected",
    [
        ("local", 1),
        ("development", 1),
        ("test", 1),
        ("staging", 2),
        ("production", 2),
    ],
)
def test_job_repository_uses_full_fsync_for_network_deployments(
    tmp_path, monkeypatch, environment, expected
):
    monkeypatch.setenv("IFCFDS_ENV", environment)
    repository = JobRepository(root=tmp_path)
    with repository._get_connection() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA synchronous").fetchone()[0] == expected


def test_repository_commits_then_reloads_job_under_production_sync_mode(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("IFCFDS_ENV", "production")
    repository = JobRepository(root=tmp_path)
    job = {
        "id": "sync-full",
        "state": "QUEUED",
        "mode": "convert",
        "created": 1.0,
        "directory": str(tmp_path / "job-sync-full"),
        "last_accessed": 1.0,
        "durable": True,
    }
    repository.register("sync-full", job)
    assert repository.get("sync-full")["state"] == "QUEUED"
    updated = dict(job, state="COMPLETED", finished=2.0)
    repository.set_durable("sync-full", updated)
    reloaded = JobRepository(root=tmp_path)
    assert reloaded.get("sync-full")["state"] == "COMPLETED"
    with reloaded._get_connection() as db:
        assert db.execute("PRAGMA synchronous").fetchone()[0] == 2
