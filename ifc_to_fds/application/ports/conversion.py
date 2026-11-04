"""Application-owned conversion protocols (R10-02)."""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingPlan, MappingManifest


@runtime_checkable
class ModelPreparerPort(Protocol):
    def prepare(self, paths: list[str], configuration: dict[str, Any]) -> CanonicalModel: ...


@runtime_checkable
class MappingPlannerPort(Protocol):
    def plan(self, model: CanonicalModel, *, cell_size: float) -> MappingPlan: ...


@runtime_checkable
class VerifiedFdsSerializerPort(Protocol):
    def serialize(
        self, model: CanonicalModel, *, cell_size: float, mapping_plan: MappingPlan
    ) -> tuple[str, MappingManifest]: ...


@runtime_checkable
class GeometryPackageWriterPort(Protocol):
    def write(self, model: CanonicalModel, path: Path, owner: Any | None) -> dict[str, Any]: ...
