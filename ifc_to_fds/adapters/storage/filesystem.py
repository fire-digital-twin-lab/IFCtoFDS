"""Local filesystem implementation of ArtifactRepositoryPort."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Union
from uuid import uuid4

from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.geometry.storage import archive_package, copy_package, file_hash


class LocalFilesystemArtifactRepository:
    """Stores run artifacts in the local filesystem."""

    def save_run_artifacts(
        self, result: Dict[str, Any], output: Union[str, Path]
    ) -> Dict[str, str]:
        target_path = Path(output).resolve()
        target_dir = target_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        base_stem = target_path.stem

        # Use an isolated staging directory in the same filesystem for atomic publication
        staging_dir = target_dir / f".staging-{uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        emitted_filenames: List[str] = [target_path.name]
        try:
            # 1. Staging write: FDS simulation input
            staging_fds = staging_dir / target_path.name
            staging_fds.write_bytes(result["fds_text"].encode("utf-8"))

            # 2. Staging write: Standard JSON artifacts
            for suffix, key in (
                ("_manifest.json", "manifest"),
                ("_acceptance_report.json", "report"),
                ("_inventory.json", "inventory"),
                ("_mep_graph.json", "mep_graph"),
                ("_configuration.json", "configuration"),
                ("_timings.json", "timings"),
                ("_parity.json", "parity_report"),
            ):
                fname = f"{base_stem}{suffix}"
                emitted_filenames.append(fname)
                (staging_dir / fname).write_text(
                    json.dumps(result[key], ensure_ascii=False, indent=2), encoding="utf-8"
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

            # 6. Atomic publication: commit all files into target_dir
            staging_payloads = staging_dir / f"{base_stem}_geometry.payloads"
            if staging_payloads.is_dir():
                target_payloads = target_dir / f"{base_stem}_geometry.payloads"
                if target_payloads.exists():
                    shutil.rmtree(target_payloads, ignore_errors=True)
                shutil.move(str(staging_payloads), str(target_payloads))

            for fname in emitted_filenames:
                src = staging_dir / fname
                dst = target_dir / fname
                # Atomic file replace within same filesystem
                src.replace(dst)

            return checksums
        finally:
            # Always clean up the temporary staging directory on completion or failure
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    def read_artifact(self, path: Union[str, Path]) -> bytes:
        return Path(path).read_bytes()
