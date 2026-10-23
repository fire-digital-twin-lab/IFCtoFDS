"""Conversion checkpoint storage; incomplete outputs remain explicitly unaccepted."""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

from ifc_to_fds.modules.artifacts.contracts import CheckpointPayload
from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.modules.geometry.api import write_package


class LocalConversionWorkspace:
    def __init__(self, output_directory=None):
        self.owner = tempfile.TemporaryDirectory(prefix="ifcfds-artifacts-") if output_directory is None else None
        self.directory = Path(self.owner.name if self.owner is not None else output_directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def write_geometry(self, model, fds_text):
        self._draft("GEOMETRY", "New geometry write started; independent audit has not completed")
        package = write_package(model, self.directory / "model_geometry.json", self.owner)
        (self.directory / "model.fds").write_bytes(fds_text.encode("utf-8"))
        return package

    def checkpoint(self, payload: CheckpointPayload, manifest):
        self._draft("VALIDATION", "Artifacts being saved; independent audit has not completed",
                    manifest.bundle_sha256)
        path = self.directory / "model_manifest.json"
        self._write_text(path, manifest.model_dump_json())
        for name, value in (
            ("inventory", payload.inventory),
            ("mep_graph", payload.mep_graph),
            ("configuration", payload.configuration),
        ):
            self._write_text(self.directory / f"model_{name}.json", json.dumps(value, allow_nan=False))
        return MappingManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def read_fds(self):
        return (self.directory / "model.fds").read_bytes().decode("utf-8")

    def complete(self, manifest, report, timings):
        self._draft("VALIDATION", "Final validation artifacts being saved", manifest.bundle_sha256)
        self._write_text(self.directory / "model_manifest.json", manifest.model_dump_json())
        sealed = (report.status.value == "MAPPING_VERIFIED" and manifest.output_complete
                  and manifest.bundle_sha256 == manifest.compute_bundle_sha256())
        invalid_completion = report.status.value == "MAPPING_VERIFIED" and not sealed
        self._state({
            "stage": "VALIDATION", "status": "INCONCLUSIVE" if invalid_completion else report.status.value,
            "checkpoint_status": "VERIFIED_SEALED" if sealed else "DRAFT_NOT_SEALED",
            "output_complete": False if invalid_completion else manifest.output_complete,
            "bundle_sha256": manifest.bundle_sha256, "timings": timings,
        })

    def _state(self, data):
        self._write_text(self.directory / "audit-state.json", json.dumps(data, allow_nan=False))

    def _draft(self, stage, reason, bundle_sha256=None):
        self._state({
            "stage": stage, "status": "NOT_RUN", "checkpoint_status": "DRAFT_NOT_SEALED",
            "output_complete": False, "bundle_sha256": bundle_sha256, "reason": reason,
        })

    def _write_text(self, path, text):
        temporary = path.with_name(f".{path.name}-{uuid4().hex}.tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


class LocalConversionWorkspaces:
    def open(self, output_directory=None):
        return LocalConversionWorkspace(output_directory)
