"""Local filesystem implementation of ArtifactRepositoryPort."""

import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Union
from uuid import uuid4

from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.modules.geometry.api import archive_package, copy_package, file_hash, read_package, verify_package, DiskPackage, payload_dir

JSON_ARTIFACTS = (
    ("_manifest.json", "manifest"),
    ("_acceptance_report.json", "report"),
    ("_inventory.json", "inventory"),
    ("_mep_graph.json", "mep_graph"),
    ("_configuration.json", "configuration"),
    ("_timings.json", "timings"),
    ("_parity.json", "parity_report"),
)


def _target(output):
    path = Path(output).resolve()
    if path.suffix.lower() != ".fds":
        raise ValueError("Artifact output must have a .fds extension")
    return path


def _artifact_filenames(target):
    return [target.name, *(target.stem + suffix for suffix, _ in JSON_ARTIFACTS),
            *(target.stem + suffix for suffix in (
                "_manifest.csv", "_acceptance_report.md", "_geometry.json", "_geometry.zip"))]


def _verify_staged_geometry(path):
    package = read_package(path)
    verify_package(package)
    if isinstance(package, DiskPackage):
        linked = {
            ref["payload"] + ".bin"
            for entry in package.index["elements"].values()
            for ref in [entry.get("mesh"), *entry.get("openings", {}).values()]
            if ref is not None
        }
        # Reused workspaces can retain old content-addressed blobs. They are
        # not part of this run, and must not enter a published geometry folder.
        for payload in payload_dir(path).iterdir():
            if payload.name not in linked:
                if not payload.is_file() or payload.is_symlink():
                    raise ValueError("Unexpected geometry payload entry")
                payload.unlink()


@contextmanager
def _publication_lock(target):
    # Exclusive creation works across threads and processes. A process crash
    # leaves a lock for explicit recovery; never guess that a writer is stale.
    lock = target.parent / f".publish-{target.stem}.lock"
    try:
        stream = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise FileExistsError(f"Artifact publication or verification in progress: {target.name}") from None
    try:
        with stream:
            json.dump({"pid": os.getpid(), "target": target.name}, stream)
        yield
    finally:
        lock.unlink(missing_ok=True)


class LocalFilesystemArtifactRepository:
    """Stores run artifacts in the local filesystem."""

    def save_run_artifacts(
        self, result: Dict[str, Any], output: Union[str, Path]
    ) -> Dict[str, str]:
        target_path = _target(output)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with _publication_lock(target_path):
            return self._save_run_artifacts(result, target_path)

    def _save_run_artifacts(self, result, target_path):
        target_dir = target_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        base_stem = target_path.stem

        # Keep staging on the same filesystem for atomic individual replacements.
        staging_dir = target_dir / f".staging-{uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        emitted_filenames: List[str] = [target_path.name]
        try:
            # 1. Staging write: FDS simulation input
            staging_fds = staging_dir / target_path.name
            staging_fds.write_bytes(result["fds_text"].encode("utf-8"))

            # 2. Staging write: Standard JSON artifacts
            for suffix, key in JSON_ARTIFACTS:
                fname = f"{base_stem}{suffix}"
                emitted_filenames.append(fname)
                (staging_dir / fname).write_text(
                    json.dumps(result[key], ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
                )

            # 3. Staging write: Manifest CSV and Markdown report
            manifest_csv_name = f"{base_stem}_manifest.csv"
            emitted_filenames.append(manifest_csv_name)
            (staging_dir / manifest_csv_name).write_bytes(
                MappingManifest.model_validate(result["manifest"]).to_csv().encode("utf-8")
            )

            report_md_name = f"{base_stem}_acceptance_report.md"
            emitted_filenames.append(report_md_name)
            (staging_dir / report_md_name).write_text(
                result["markdown_report"], encoding="utf-8"
            )

            # 4. Staging write: Geometry package and archive
            geom_json_name = f"{base_stem}_geometry.json"
            emitted_filenames.append(geom_json_name)
            staging_geom_json = staging_dir / geom_json_name
            copy_package(result["geometry_package"], staging_geom_json)
            # Reopen staged bytes: the caller's cached package may predate a
            # changed index or damaged payload. Fail before altering the target.
            _verify_staged_geometry(staging_geom_json)

            geom_zip_name = f"{base_stem}_geometry.zip"
            emitted_filenames.append(geom_zip_name)
            archive_package(staging_geom_json, staging_dir / geom_zip_name)

            # 5. Staging write: Isolated, deterministic checksums of emitted artifacts only
            checksums = {
                fname: file_hash(staging_dir / fname)
                for fname in emitted_filenames
            }
            checksums_name = f"{base_stem}_checksums.json"
            (staging_dir / checksums_name).write_text(
                json.dumps(checksums, indent=2), encoding="utf-8"
            )
            emitted_filenames.append(checksums_name)

            # 6. Serialized publication with rollback protection (not crash-atomic).
            backup_dir = target_dir / f".backup-{uuid4().hex}"
            existing_backed_up: List[str] = []
            target_payloads = target_dir / f"{base_stem}_geometry.payloads"
            backup_payloads = backup_dir / f"{base_stem}_geometry.payloads"
            has_existing_payloads = target_payloads.is_dir()
            published_files: List[str] = []
            payloads_changed = False
            retain_backup = False

            try:
                # 6a. Backup any pre-existing files to protect against partial overwrite failure
                for fname in emitted_filenames:
                    dest_file = target_dir / fname
                    if dest_file.exists():
                        backup_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(dest_file, backup_dir / fname)
                        existing_backed_up.append(fname)
                if has_existing_payloads:
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(target_payloads, backup_payloads, dirs_exist_ok=True)

                # 6b. Move geometry payloads
                staging_payloads = staging_dir / f"{base_stem}_geometry.payloads"
                if staging_payloads.is_dir() or has_existing_payloads:
                    payloads_changed = True
                    if target_payloads.exists():
                        shutil.rmtree(target_payloads)
                    if staging_payloads.is_dir():
                        shutil.move(str(staging_payloads), str(target_payloads))

                # 6c. Move all artifact files
                for fname in emitted_filenames:
                    src = staging_dir / fname
                    dst = target_dir / fname
                    src.replace(dst)
                    published_files.append(fname)

                # 6d. Commit successful: clean up backup directory
                if backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)

                return checksums

            except Exception as publication_error:
                # Transaction failed: Rollback changes to avoid corrupted or mixed bundles
                # A failed backup has not changed the destination. Restore only
                # things actually published, never delete untouched payloads.
                try:
                    for fname in published_files:
                        if fname in existing_backed_up:
                            shutil.copy2(backup_dir / fname, target_dir / fname)
                        else:
                            (target_dir / fname).unlink(missing_ok=True)
                    if payloads_changed:
                        if target_payloads.exists():
                            shutil.rmtree(target_payloads)
                        if has_existing_payloads:
                            shutil.copytree(backup_payloads, target_payloads)
                except Exception as rollback_error:
                    retain_backup = True
                    raise RuntimeError(
                        f"Artifact publication failed ({publication_error}); rollback failed "
                        f"({rollback_error}). Original backup retained at {backup_dir}"
                    ) from publication_error
                raise
            finally:
                if not retain_backup and backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)
        finally:
            # Always clean up the temporary staging directory on completion or failure
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    def read_artifact(self, path: Union[str, Path]) -> bytes:
        return Path(path).read_bytes()


def verify_run_artifacts(output):
    """Verify saved bytes and geometry payloads; never grant mapping acceptance."""
    target = _target(output)
    with _publication_lock(target):
        try:
            checksums = json.loads(target.with_name(target.stem + "_checksums.json").read_text(encoding="utf-8"))
            # Use the fixed output contract, never arbitrary paths supplied by
            # a checksum document. Extra unrelated files are outside this scope.
            if not isinstance(checksums, dict) or set(checksums) != set(_artifact_filenames(target)):
                raise ValueError("Artifact checksum inventory differs from the output contract")
            for name, expected in checksums.items():
                if (not isinstance(expected, str) or len(expected) != 64
                        or any(c not in "0123456789abcdef" for c in expected)):
                    raise ValueError(f"Invalid artifact checksum: {name}")
                if file_hash(target.parent / name) != expected:
                    raise ValueError(f"Artifact checksum mismatch: {name}")
            verify_package(read_package(target.with_name(target.stem + "_geometry.json")))
        except (OSError, TypeError, KeyError) as exc:
            raise ValueError(f"Invalid artifact bundle: {exc}") from exc
    return {"status": "PASS", "scope": "ARTIFACT_BYTES_AND_GEOMETRY_PAYLOAD_INTEGRITY",
            "files": checksums}
