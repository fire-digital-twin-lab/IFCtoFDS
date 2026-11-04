"""Local filesystem adapter for the two-stage verified conversion checkpoint.

Preserves legacy filenames and serialization. The source auditor must read
the persisted FDS bytes and MappingManifest, not converter in-memory objects.
"""

import hashlib
import json
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from ifc_to_fds.application.services.portable_inventory import compact_inventory
from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest, MappingPlan


def _atomic_write_text(path: Path, content: str) -> None:
    """Replace a single checkpoint atomically without leaving a truncated file."""
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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
        # Fail closed before persisting ANY final artifact. A text status alone
        # must never seal a bundle with incomplete or inconsistent evidence.
        sealed = status == "MAPPING_VERIFIED"
        if sealed:
            if (
                manifest.output_complete is not True
                or manifest.mapping_acceptance != "MAPPING_VERIFIED"
                or manifest.acceptance_status != "MAPPING_VERIFIED"
            ):
                raise ValueError(
                    "Cannot seal mapping: audit status and manifest acceptance disagree"
                )
            digest = manifest.bundle_sha256
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
                or manifest.compute_bundle_sha256() != digest
            ):
                raise ValueError("Cannot seal mapping: manifest bundle hash is invalid")
            fds_path = self.directory / "model.fds"
            if not fds_path.is_file() or (
                hashlib.sha256(fds_path.read_bytes()).hexdigest()
                != manifest.fds_sha256
            ):
                raise ValueError("Cannot seal mapping: persisted FDS hash differs")

        checkpoint = {
            "stage": "VALIDATION",
            "status": status,
            "checkpoint_status": (
                "VERIFIED_SEALED" if sealed else "DRAFT_NOT_SEALED"
            ),
            "output_complete": manifest.output_complete,
            "bundle_sha256": manifest.bundle_sha256,
            "timings": timings,
        }
        # Persist the manifest first and checkpoint LAST: a crash between the
        # two leaves an unsealed checkpoint rather than false verification.
        _atomic_write_text(
            self.directory / "model_manifest.json",
            manifest.model_dump_json(),
        )
        _atomic_write_text(
            self.directory / "audit-state.json",
            json.dumps(checkpoint),
        )


class LocalConversionWorkspaceFactory:
    """Composition-root adapter for durable or temporary local workspaces."""

    def create(self, output_directory: str | Path | None) -> LocalConversionWorkspace:
        return LocalConversionWorkspace(output_directory)
