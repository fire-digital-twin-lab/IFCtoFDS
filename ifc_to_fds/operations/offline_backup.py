"""Explicit offline backup/restore for the single-instance SQLite job store.

This is a recovery utility, not a live distributed snapshot mechanism.
Operators MUST stop the API and workers before invoking either command.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import sys


class OfflineBackupError(RuntimeError):
    """A backup or restoration cannot be completed without risking integrity."""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sqlite_integrity(path: Path) -> None:
    try:
        with closing(sqlite3.connect(str(path))) as connection:
            results = [row[0] for row in connection.execute("PRAGMA integrity_check")]
            if results != ["ok"]:
                raise OfflineBackupError("SQLite integrity_check failed")
    except sqlite3.DatabaseError as exc:
        raise OfflineBackupError("Cannot verify SQLite database integrity") from exc


def _validated_path(relative: str) -> PurePosixPath:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise OfflineBackupError("Invalid backup path")
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or str(path) != relative
        or any(part in ("", ".", "..") or ":" in part for part in path.parts)
    ):
        raise OfflineBackupError("Unsafe backup path")
    if relative != "jobs.sqlite3" and (
        len(path.parts) < 2 or not path.parts[0].startswith("job-")
    ):
        raise OfflineBackupError("Backup contains a path outside job artifacts")
    return path


def _require_regular_no_links(path: Path, root: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise OfflineBackupError(f"Missing, non-file or symbolic link: {path.name}")
    current = path.parent
    while current != root:
        if current.is_symlink() or not current.is_dir():
            raise OfflineBackupError("Backup includes a symbolic-link directory")
        if root not in current.parents:
            raise OfflineBackupError("Backup path escaped the expected root")
        current = current.parent


def _copy_checked(source: Path, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as read, destination.open("xb") as write:
        shutil.copyfileobj(read, write, length=1024 * 1024)
        write.flush()
        os.fsync(write.fileno())
    digest = _hash_file(destination)
    if _hash_file(source) != digest:
        raise OfflineBackupError("File changed during backup; keep service stopped")
    return {"sha256": digest, "size": destination.stat().st_size}


def _validate_terminal_rows(db: Path, root: Path) -> int:
    try:
        with closing(sqlite3.connect(str(db))) as connection:
            rows = connection.execute("SELECT id, state, directory FROM jobs").fetchall()
    except sqlite3.DatabaseError as exc:
        raise OfflineBackupError("Cannot read job metadata") from exc
    for jid, state, directory in rows:
        if state in ("QUEUED", "RUNNING"):
            raise OfflineBackupError(
                "Active jobs exist; stop the scheduler and finish/cancel jobs first"
            )
        location = Path(directory)
        if location.parent.resolve() != root or not location.name.startswith("job-"):
            raise OfflineBackupError(f"Job {jid} uses a directory outside the job root")
        if not location.is_dir() or location.is_symlink():
            raise OfflineBackupError(f"Job {jid} has a missing or unsafe artifact directory")
    return len(rows)


def create_offline_backup(job_root: Path | str, destination: Path | str) -> dict:
    """Create a complete backup directory, publishing manifest.json last.

    Requires the API/scheduler/workers to be stopped externally. This function
    refuses active SQLite rows but cannot prove another process is not running.
    """
    supplied = Path(job_root)
    if supplied.is_symlink():
        raise OfflineBackupError("Job root cannot be a symbolic link")
    root = supplied.resolve(strict=True)
    target = Path(destination).resolve()
    if not root.is_dir() or not (root / "jobs.sqlite3").is_file():
        raise OfflineBackupError("Expected job root with jobs.sqlite3")
    if target.exists() or target == root or root in target.parents:
        raise OfflineBackupError("Backup destination must not exist or be inside job root")
    db = root / "jobs.sqlite3"
    _require_regular_no_links(db, root)
    _sqlite_integrity(db)
    count = _validate_terminal_rows(db, root)

    artifacts = []
    for directory in sorted(root.glob("job-*")):
        if directory.is_symlink() or not directory.is_dir():
            raise OfflineBackupError("Unexpected symbolic link or non-directory job entry")
        for item in sorted(directory.rglob("*")):
            if item.is_symlink():
                raise OfflineBackupError("Symbolic links are not permitted in job artifacts")
            if item.is_file():
                _require_regular_no_links(item, root)
                artifacts.append(item)
            elif not item.is_dir():
                raise OfflineBackupError("Unsupported filesystem object in job artifacts")

    target.mkdir(parents=True, exist_ok=False)
    entries = []
    # sqlite3.backup reads committed WAL data rather than blindly copying
    # jobs.sqlite3 while a WAL file may still exist.
    snapshot = target / "jobs.sqlite3"
    try:
        with closing(sqlite3.connect(str(db), timeout=10.0)) as source:
            with closing(sqlite3.connect(str(snapshot))) as dest:
                source.backup(dest)
                dest.commit()
        _sqlite_integrity(snapshot)
    except sqlite3.Error as exc:
        raise OfflineBackupError("SQLite snapshot failed; partial backup has no manifest") from exc

    entries.append({
        "path": "jobs.sqlite3",
        "sha256": _hash_file(snapshot),
        "size": snapshot.stat().st_size,
    })
    for file in artifacts:
        relative = file.relative_to(root).as_posix()
        _validated_path(relative)
        metadata = _copy_checked(file, target / relative)
        entries.append({"path": relative, **metadata})

    manifest = {
        "schema": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "original_job_root": str(root),
        "job_count": count,
        "files": sorted(entries, key=lambda item: item["path"]),
        "status": "OFFLINE_SNAPSHOT_ONLY",
    }
    staged = target / "manifest.json.tmp"
    with staged.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    staged.replace(target / "manifest.json")
    return manifest


def _check_backup_files(source: Path, manifest: dict) -> list[dict]:
    if manifest.get("schema") != 1 or not isinstance(manifest.get("files"), list):
        raise OfflineBackupError("Unsupported backup manifest format")
    files = manifest["files"]
    if not files:
        raise OfflineBackupError("Empty backup manifest")
    seen = set()
    for item in files:
        if not isinstance(item, dict):
            raise OfflineBackupError("Malformed backup manifest entry")
        raw = item.get("path")
        rel = _validated_path(raw)
        if raw in seen:
            raise OfflineBackupError("Duplicate path in backup manifest")
        seen.add(raw)
        path = source.joinpath(*rel.parts)
        _require_regular_no_links(path, source)
        if (
            item.get("size") != path.stat().st_size
            or item.get("sha256") != _hash_file(path)
        ):
            raise OfflineBackupError("Backup checksum or length mismatch")
    if "jobs.sqlite3" not in seen:
        raise OfflineBackupError("Backup is missing SQLite metadata")
    for path in source.rglob("*"):
        if path.is_symlink():
            raise OfflineBackupError("Backup contains a symbolic link")
        if path.is_file() and path.relative_to(source).as_posix() not in seen | {"manifest.json"}:
            raise OfflineBackupError("Unexpected unmanifested backup file")
    _sqlite_integrity(source / "jobs.sqlite3")
    return files


def restore_offline_backup(source_dir: Path | str, target_root: Path | str) -> dict:
    """Verify all checksums before restoring to a NEW, nonexistent directory."""
    supplied = Path(source_dir)
    if supplied.is_symlink():
        raise OfflineBackupError("Backup root cannot be a symbolic link")
    source = supplied.resolve(strict=True)
    target = Path(target_root).resolve()
    if not source.is_dir() or not (source / "manifest.json").is_file():
        raise OfflineBackupError("Missing backup manifest")
    if target.exists() or target == source or source in target.parents:
        raise OfflineBackupError("Restore destination must not exist or be inside backup")
    manifest_file = source / "manifest.json"
    _require_regular_no_links(manifest_file, source)
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OfflineBackupError("Invalid backup manifest") from exc
    files = _check_backup_files(source, manifest)
    target.mkdir(parents=True, exist_ok=False)
    for item in files:
        rel = _validated_path(item["path"])
        copy = _copy_checked(source.joinpath(*rel.parts), target.joinpath(*rel.parts))
        if copy["sha256"] != item["sha256"]:
            raise OfflineBackupError("Restored file integrity mismatch")

    # The metadata stores absolute directory paths. Relocate each terminal job
    # within the fresh root; never carry over the old host's artifact paths.
    original_root = str(manifest.get("original_job_root", "")).replace("\\", "/").rstrip("/")
    if not original_root:
        raise OfflineBackupError("Backup lacks original job-root provenance")
    db = target / "jobs.sqlite3"
    with closing(sqlite3.connect(str(db))) as connection:
        rows = connection.execute("SELECT id, state, directory FROM jobs").fetchall()
        for jid, state, directory in rows:
            if state in ("QUEUED", "RUNNING"):
                raise OfflineBackupError("Backup contains an active job")
            normalized = str(directory).replace("\\", "/").rstrip("/")
            prefix = original_root + "/"
            if not normalized.startswith(prefix):
                raise OfflineBackupError("Metadata directory does not match original root")
            dirname = normalized[len(prefix):]
            if "/" in dirname or not dirname.startswith("job-"):
                raise OfflineBackupError("Metadata contains an unsafe artifact directory")
            if not (target / dirname).is_dir():
                raise OfflineBackupError("Restored artifact directory is missing")
            connection.execute(
                "UPDATE jobs SET directory = ? WHERE id = ?",
                (str(target / dirname), jid),
            )
        connection.commit()
    _sqlite_integrity(db)
    return {"job_count": len(rows), "restored_to": str(target), "verified": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    backup = actions.add_parser("backup", help="Offline backup; API/workers must be stopped")
    backup.add_argument("--job-root", required=True)
    backup.add_argument("--destination", required=True)
    restore = actions.add_parser("restore", help="Restore to a NEW empty location")
    restore.add_argument("--source", required=True)
    restore.add_argument("--destination", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "backup":
            result = create_offline_backup(args.job_root, args.destination)
        else:
            result = restore_offline_backup(args.source, args.destination)
    except (OfflineBackupError, OSError, sqlite3.Error) as exc:
        print(f"Backup/restore rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
