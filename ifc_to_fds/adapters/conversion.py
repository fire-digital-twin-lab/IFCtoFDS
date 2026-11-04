"""Production conversion adapters; authoritative algorithms remain unchanged."""
from pathlib import Path
from typing import Any
from ifc_to_fds.application.services.model_preparer import prepare_model
from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingPlan, MappingManifest, build_mapping_plan
from ifc_to_fds.geometry.storage import write_package
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mep.network import build_hvac_network

class DefaultModelPreparer:
    def prepare(self, paths: list[str], configuration: dict[str, Any]) -> CanonicalModel:
        return prepare_model(paths, configuration)

class DefaultMappingPlanner:
    def plan(self, model: CanonicalModel, *, cell_size: float) -> MappingPlan:
        return build_mapping_plan(model, cell_size=cell_size, hvac_network=build_hvac_network(model))

class DefaultFdsSerializer:
    def serialize(self, model: CanonicalModel, *, cell_size: float, mapping_plan: MappingPlan) -> tuple[str, MappingManifest]:
        return serialize_fds(model, cell_size=cell_size, mapping_plan=mapping_plan)

class DefaultGeometryPackageWriter:
    def write(self, model: CanonicalModel, path: Path, owner: Any | None) -> dict[str, Any]:
        return write_package(model, path, owner)
