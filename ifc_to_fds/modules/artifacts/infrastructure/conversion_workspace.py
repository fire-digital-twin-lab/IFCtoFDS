"""Conversion checkpoint storage; incomplete outputs remain explicitly unaccepted."""

import json
import tempfile
from pathlib import Path

from ifc_to_fds.modules.artifacts.contracts import CheckpointPayload
from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.modules.geometry.api import write_package


class LocalConversionWorkspace:
    def __init__(self, output_directory=None):
        self.owner = tempfile.TemporaryDirectory(prefix="ifcfds-artifacts-") if output_directory is None else None
        self.directory = Path(self.owner.name if self.owner is not None else output_directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def write_geometry(self, model, fds_text):
        package = write_package(model, self.directory / "model_geometry.json", self.owner)
        (self.directory / "model.fds").write_bytes(fds_text.encode("utf-8"))
        return package

    def checkpoint(self, payload: CheckpointPayload, manifest):
        path = self.directory / "model_manifest.json"
        path.write_text(manifest.model_dump_json(), encoding="utf-8")
        for name, value in (
            ("inventory", payload.inventory),
            ("mep_graph", payload.mep_graph),
            ("configuration", payload.configuration),
        ):
            (self.directory / f"model_{name}.json").write_text(json.dumps(value), encoding="utf-8")
        self._state({
            "stage": "VALIDATION", "status": "NOT_RUN",
            "checkpoint_status": "DRAFT_NOT_SEALED", "output_complete": False,
            "bundle_sha256": manifest.bundle_sha256,
            "reason": "Artifacts saved; independent audit has not completed",
        })
        return MappingManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def read_fds(self):
        return (self.directory / "model.fds").read_bytes().decode("utf-8")

    def complete(self, manifest, report, timings):
        (self.directory / "model_manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
        self._state({
            "stage": "VALIDATION", "status": report.status.value,
            "checkpoint_status": "DRAFT_NOT_SEALED" if report.status.value != "MAPPING_VERIFIED" else "VERIFIED_SEALED",
            "output_complete": manifest.output_complete,
            "bundle_sha256": manifest.bundle_sha256, "timings": timings,
        })

    def _state(self, data):
        (self.directory / "audit-state.json").write_text(json.dumps(data), encoding="utf-8")


class LocalConversionWorkspaces:
    def open(self, output_directory=None):
        return LocalConversionWorkspace(output_directory)
