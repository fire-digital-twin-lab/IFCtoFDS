"""Offline snapshot and restore must reject corruption or unsafe destinations."""

import json
import os
import time

import pytest

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.operations.offline_backup import (
    OfflineBackupError,
    create_offline_backup,
    restore_offline_backup,
)


def _store(tmp_path, *, state="COMPLETED"):
    root = tmp_path / "jobs"
    root.mkdir()
    directory = root / "job-reference"
    directory.mkdir()
    artifact = directory / "result.json"
    artifact.write_text('{"status":"INCONCLUSIVE","artifacts":{}}', encoding="utf-8")
    (directory / "source-reference.ifc").write_bytes(b"IFC fixture data")
    now = time.time()
    repo = JobRepository(root=root)
    repo.register(
        "reference",
        {
            "id": "reference",
            "state": state,
            "mode": "convert",
            "directory": str(directory),
            "created": now - 120,
            "started": now - 90,
            "finished": now - 60 if state == "COMPLETED" else None,
            "last_accessed": now,
            "process": None,
        },
    )
    return root, artifact


def test_offline_backup_restores_sqlite_and_artifacts_with_relocated_paths(tmp_path):
    root, artifact = _store(tmp_path)
    backup = tmp_path / "backup"
    restore = tmp_path / "restored"

    manifest = create_offline_backup(root, backup)
    assert manifest["schema"] == 2
    assert "job-reference" in manifest["directories"]
    assert manifest["job_count"] == 1
    assert (backup / "manifest.json").is_file()
    assert (backup / "jobs.sqlite3").is_file()

    result = restore_offline_backup(backup, restore)
    assert result["verified"] is True
    assert result["job_count"] == 1
    restored_job = JobRepository(root=restore).get("reference")
    assert restored_job is not None
    assert restored_job["state"] == "COMPLETED"
    assert restored_job["directory"] == str(restore / "job-reference")
    assert (restore / "job-reference" / "result.json").read_bytes() == artifact.read_bytes()
    assert (restore / "job-reference" / "source-reference.ifc").read_bytes() == b"IFC fixture data"


def test_backup_refuses_active_jobs_and_leaves_destination_uncreated(tmp_path):
    root, _ = _store(tmp_path, state="QUEUED")
    backup = tmp_path / "backup"
    with pytest.raises(OfflineBackupError, match="Active jobs"):
        create_offline_backup(root, backup)
    assert not backup.exists()


def test_corrupt_artifact_fails_before_creating_restore_destination(tmp_path):
    root, _ = _store(tmp_path)
    backup = tmp_path / "backup"
    create_offline_backup(root, backup)
    (backup / "job-reference" / "result.json").write_bytes(b"tampered")
    restored = tmp_path / "restored"
    with pytest.raises(OfflineBackupError, match="checksum or length"):
        restore_offline_backup(backup, restored)
    assert not restored.exists()


def test_restore_refuses_to_overwrite_existing_data(tmp_path):
    root, _ = _store(tmp_path)
    backup = tmp_path / "backup"
    create_offline_backup(root, backup)
    restored = tmp_path / "restored"
    restored.mkdir()
    sentinel = restored / "keep.txt"
    sentinel.write_text("never overwrite", encoding="utf-8")
    with pytest.raises(OfflineBackupError, match="must not exist"):
        restore_offline_backup(backup, restored)
    assert sentinel.read_text(encoding="utf-8") == "never overwrite"


def test_backup_refuses_to_write_inside_source_store(tmp_path):
    root, _ = _store(tmp_path)
    with pytest.raises(OfflineBackupError, match="inside job root"):
        create_offline_backup(root, root / "accidental-backup")
    assert not (root / "accidental-backup").exists()


def test_restore_rejects_path_traversal_in_manifest(tmp_path):
    root, _ = _store(tmp_path)
    backup = tmp_path / "backup"
    create_offline_backup(root, backup)
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][1]["path"] = "../escape.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    target = tmp_path / "restored"
    with pytest.raises(OfflineBackupError, match="Unsafe backup path"):
        restore_offline_backup(backup, target)
    assert not target.exists()
    assert not (tmp_path / "escape.txt").exists()


def test_backup_refuses_symbolic_links_inside_artifacts(tmp_path):
    root, _ = _store(tmp_path)
    outside = tmp_path / "private.txt"
    outside.write_text("must never be copied", encoding="utf-8")
    link = root / "job-reference" / "external-link"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks requires OS privilege on this runner")
    backup = tmp_path / "backup"
    with pytest.raises(OfflineBackupError, match="Symbolic links"):
        create_offline_backup(root, backup)
    assert not backup.exists()


def test_empty_job_directory_and_empty_nested_folders_are_restored(tmp_path):
    root, artifact = _store(tmp_path)
    artifact.unlink()
    (root / "job-reference" / "source-reference.ifc").unlink()
    (root / "job-reference" / "empty-inner").mkdir()
    backup = tmp_path / "backup"
    manifest = create_offline_backup(root, backup)

    assert "job-reference" in manifest["directories"]
    assert "job-reference/empty-inner" in manifest["directories"]
    restored = tmp_path / "restored"
    result = restore_offline_backup(backup, restored)
    assert result["job_count"] == 1
    assert (restored / "job-reference" / "empty-inner").is_dir()
    assert JobRepository(root=restored).get("reference")["directory"] == str(
        restored / "job-reference"
    )


def test_restore_rejects_unmanifested_directory_before_creating_target(tmp_path):
    root, _ = _store(tmp_path)
    backup = tmp_path / "backup"
    create_offline_backup(root, backup)
    (backup / "job-injected").mkdir()
    restored = tmp_path / "restored"
    with pytest.raises(OfflineBackupError, match="unmanifested backup directory"):
        restore_offline_backup(backup, restored)
    assert not restored.exists()


def test_restore_rejects_traversal_in_directory_manifest(tmp_path):
    root, _ = _store(tmp_path)
    backup = tmp_path / "backup"
    create_offline_backup(root, backup)
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["directories"][0] = "../outside"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    restored = tmp_path / "restored"
    with pytest.raises(OfflineBackupError, match="Unsafe backup path"):
        restore_offline_backup(backup, restored)
    assert not restored.exists()
