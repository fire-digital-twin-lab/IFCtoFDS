"""Small ports consumed by conversion orchestration."""

from pathlib import Path
from typing import Any, Protocol

from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.domain.validation import AcceptanceReport
from ifc_to_fds.modules.artifacts.contracts import CheckpointPayload


class ModelPreparationPort(Protocol):
    def prepare(self, paths: list[str], configuration: dict[str, Any], reference: bool = False) -> CanonicalModel: ...


class ConversionWorkspace(Protocol):
    def write_geometry(self, model: CanonicalModel, fds_text: str) -> Any: ...

    def checkpoint(self, payload: CheckpointPayload, manifest: MappingManifest) -> MappingManifest: ...

    def read_fds(self) -> str: ...

    def complete(self, manifest: MappingManifest, report: AcceptanceReport, timings: dict[str, Any]) -> None: ...


class ConversionWorkspacePort(Protocol):
    def open(self, output_directory: str | Path | None) -> ConversionWorkspace: ...


class ValidationEnginePort(Protocol):
    def validate(self, model: CanonicalModel, fds_text: str, manifest: MappingManifest, config: Any) -> AcceptanceReport: ...
