"""Local filesystem implementation of ArtifactRepositoryPort."""

import json
from pathlib import Path
from typing import Any, Dict, Union

from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.geometry.storage import archive_package, copy_package, file_hash


class LocalFilesystemArtifactRepository:
    """Stores run artifacts in the local filesystem."""

    def save_run_artifacts(
        self, result: Dict[str, Any], output: Union[str, Path]
    ) -> Dict[str, str]:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result["fds_text"].encode("utf-8"))
        base = path.with_suffix("")
        for suffix, key in (
            ("_manifest.json", "manifest"),
            ("_acceptance_report.json", "report"),
            ("_inventory.json", "inventory"),
            ("_mep_graph.json", "mep_graph"),
            ("_configuration.json", "configuration"),
            ("_timings.json", "timings"),
            ("_parity.json", "parity_report"),
        ):
            Path(str(base) + suffix).write_text(
                json.dumps(result[key], ensure_ascii=False, indent=2), encoding="utf-8"
            )
        Path(str(base) + "_manifest.csv").write_bytes(
            MappingManifest.model_validate(result["manifest"]).to_csv().encode("utf-8")
        )
        Path(str(base) + "_acceptance_report.md").write_text(
            result["markdown_report"], encoding="utf-8"
        )

        geometry_path = Path(str(base) + "_geometry.json")
        copy_package(result["geometry_package"], geometry_path)
        archive_package(geometry_path, Path(str(base) + "_geometry.zip"))

        checksums = {
            f.name: file_hash(f)
            for f in path.parent.glob(base.name + "*")
            if f.is_file() and not f.name.endswith("_checksums.json")
        }
        Path(str(base) + "_checksums.json").write_text(
            json.dumps(checksums, indent=2), encoding="utf-8"
        )
        return checksums

    def read_artifact(self, path: Union[str, Path]) -> bytes:
        return Path(path).read_bytes()
