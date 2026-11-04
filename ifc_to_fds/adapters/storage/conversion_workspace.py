"""Local filesystem adapter for the two-stage verified conversion checkpoint.

Preserves legacy filenames and serialization. The source auditor must read
the persisted FDS bytes and MappingManifest, not converter in-memory objects.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from ifc_to_fds.application.services.portable_inventory import compact_inventory
from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest, MappingPlan


class LocalConversionWorkspace:
    """One workspace; owner stays alive while its geometry package is referenced."""

    def __init__(self, output_directory: str | Path | None):
        self.owner = (
            TemporaryDirectory(prefix="ifcfds-artifacts-")
            if output_directory is None
            else None
        )
        self.directory = Path(
            self.owner.name if self.owner is not None else (output_directory or ".")
        )
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def geometry_path(self) -> Path:
        return self.directory / "model_geometry.json"

    def write_prepared(self, fds_text: str, mapping_plan: MappingPlan) -> None:
        # Preserve exact bytes, order of writes and JSON representation.
        (self.directory / "model.fds").write_bytes(fds_text.encode("utf-8"))
        (self.directory / "mapping_plan.json").write_text(
            mapping_plan.model_dump_json(), encoding="utf-8"
        )

    def write_draft(
        self, model: CanonicalModel, configuration: dict[str, Any], manifest: MappingManifest
    ) -> MappingManifest:
        manifest_path = self.directory / "model_manifest.json"
        manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
        for name, value in (
            ("inventory", compact_inventory(model)),
            ("mep_graph", configuration["mep_graph"]),
            ("configuration", configuration),
        ):
            (self.directory / f"model_{name}.json").write_text(
                json.dumps(value), encoding="utf-8"
            )
        (self.directory / "audit-state.json").write_text(
            json.dumps(
                {
                    "stage": "VALIDATION",
                    "status": "NOT_RUN",
                    "checkpoint_status": "DRAFT_NOT_SEALED",
                    "output_complete": False,
                    "bundle_sha256": manifest.bundle_sha256,
                    "reason": "Artifacts saved; independent audit has not completed",
                }
            ),
            encoding="utf-8",
        )
        # Rehydrate the serialized manifest as in the original conversion path.
        return MappingManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )

    def read_fds(self) -> str:
        return (self.directory / "model.fds").read_bytes().decode("utf-8")

    def finish_audit(
        self, manifest: MappingManifest, status: str, timings: dict[str, Any]
    ) -> None:
        (self.directory / "model_manifest.json").write_text(
            manifest.model_dump_json(), encoding="utf-8"
        )
        (self.directory / "audit-state.json").write_text(
            json.dumps(
                {
                    "stage": "VALIDATION",
                    "status": status,
                    # Mapping verification is the only currently sealed outcome.
                    "checkpoint_status": (
                        "DRAFT_NOT_SEALED"
                        if status != "MAPPING_VERIFIED"
                        else "VERIFIED_SEALED"
                    ),
                    "output_complete": manifest.output_complete,
                    "bundle_sha256": manifest.bundle_sha256,
                    "timings": timings,
                }
            ),
            encoding="utf-8",
        )


class LocalConversionWorkspaceFactory:
    """Composition-root adapter for durable or temporary local workspaces."""

    def create(self, output_directory: str | Path | None) -> LocalConversionWorkspace:
        return LocalConversionWorkspace(output_directory)
