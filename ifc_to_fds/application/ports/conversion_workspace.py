"""Application contracts for draft and audited conversion artifacts (R10-03).

The independent auditor must re-read persisted FDS and MappingManifest data.
No conversion use case should decide acceptance by inspecting its own writes.
"""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest, MappingPlan


@runtime_checkable
class ConversionWorkspacePort(Protocol):
    """Own the lifetime and I/O of one verified conversion workspace."""

    @property
    def owner(self) -> Any | None: ...

    @property
    def geometry_path(self) -> Path: ...

    def write_prepared(self, fds_text: str, mapping_plan: MappingPlan) -> None: ...

    def write_draft(
        self, model: CanonicalModel, configuration: dict[str, Any], manifest: MappingManifest
    ) -> MappingManifest: ...

    def read_fds(self) -> str: ...

    def finish_audit(
        self, manifest: MappingManifest, status: str, timings: dict[str, Any]
    ) -> None: ...


@runtime_checkable
class ConversionWorkspaceFactoryPort(Protocol):
    def create(self, output_directory: str | Path | None) -> ConversionWorkspacePort: ...
