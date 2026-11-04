"""ConvertVerified use case: end-to-end verified BIM-to-FDS conversion."""

import gc
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Union

from ifc_to_fds.domain.mapping import build_mapping_plan
from ifc_to_fds.domain.validation.model import GateResult, GateStatus
from ifc_to_fds.geometry.storage import write_package
from ifc_to_fds.mapping.exporter import serialize_fds
from ..ports.conversion import (ModelPreparerPort, MappingPlannerPort, VerifiedFdsSerializerPort, GeometryPackageWriterPort)
from ..ports.conversion_workspace import ConversionWorkspaceFactoryPort
from ..services.portable_inventory import compact_inventory

from ..dto.configuration import validate_configuration
from .audit_conversion import AuditConversionUseCase, prepare_model


class ConvertVerifiedUseCase:
    """Orchestrates verified conversion of IFC models to FDS input."""

    def __init__(
        self,
        audit_use_case: Optional[AuditConversionUseCase] = None,
        *,
        model_preparer: Optional[ModelPreparerPort] = None,
        mapping_planner: Optional[MappingPlannerPort] = None,
        fds_serializer: Optional[VerifiedFdsSerializerPort] = None,
        geometry_writer: Optional[GeometryPackageWriterPort] = None,
        workspace_factory: Optional[ConversionWorkspaceFactoryPort] = None,
    ):
        # Transitional fallback preserves direct legacy construction.
        self.audit_use_case = audit_use_case or AuditConversionUseCase()
        self.model_preparer = model_preparer
        self.mapping_planner = mapping_planner
        self.fds_serializer = fds_serializer
        self.geometry_writer = geometry_writer
        self.workspace_factory = workspace_factory

    def execute(
        self,
        paths: List[str],
        configuration: Optional[Dict[str, Any]] = None,
        output_directory: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        configuration = validate_configuration(configuration or {})
        start = perf_counter()
        model = (
            self.model_preparer.prepare(paths, configuration)
            if self.model_preparer is not None
            else prepare_model(paths, configuration)
        )
        configuration["rebase_vector"] = model.source.rebase_vector
        prepared = perf_counter()
        cell_size = configuration.get("cell_size", 0.2)
        if self.mapping_planner is not None:
            mapping_plan = self.mapping_planner.plan(model, cell_size=cell_size)
        else:
            from ifc_to_fds.mep.network import build_hvac_network
            mapping_plan = build_mapping_plan(
                model, cell_size=cell_size, hvac_network=build_hvac_network(model)
            )
        if self.fds_serializer is not None:
            fds, manifest = self.fds_serializer.serialize(
                model, cell_size=cell_size, mapping_plan=mapping_plan
            )
        else:
            fds, manifest = serialize_fds(
                model, cell_size=cell_size, mapping_plan=mapping_plan
            )
        serialized = perf_counter()

        if self.workspace_factory is not None:
            workspace = self.workspace_factory.create(output_directory)
        else:
            from ifc_to_fds.legacy_conversion_workspace import create_legacy_workspace
            workspace = create_legacy_workspace(output_directory)
        if self.geometry_writer is not None:
            geometry_package = self.geometry_writer.write(
                model, workspace.geometry_path, workspace.owner
            )
        else:
            geometry_package = write_package(
                model, workspace.geometry_path, workspace.owner
            )
        workspace.write_prepared(fds, mapping_plan)
        packaged = perf_counter()
        configuration["geometry_package_sha256"] = geometry_package["sha256"]
        manifest.geometry_package_sha256 = geometry_package["sha256"]
        configuration["mep_graph"] = model.mep_graph.model_dump(mode="json")
        manifest.configuration = configuration
        manifest.reseal()
        manifest = workspace.write_draft(model, configuration, manifest)
        # The auditor reopens the source. Release the converter's full meshes
        # before constructing that independent model, rather than retaining both.
        source_timings = dict(model.timings)
        exported_bounds = model.exported_bounds
        del mapping_plan, model
        gc.collect()
        fds = workspace.read_fds()
        audited, manifest, report = self.audit_use_case.execute(
            paths, fds, manifest, configuration, geometry_package
        )
        timings = dict(
            **source_timings,
            prepare_s=prepared - start,
            serialize_s=serialized - prepared,
            package_write_s=packaged - serialized,
            **report.metrics.get("stage_timings", {}),
            audit_s=perf_counter() - serialized,
        )
        workspace.finish_audit(manifest, report.status.value, timings)
        from ifc_to_fds.core import get_execution_provenance

        audited.exported_bounds = exported_bounds
        audited.timings = timings
        report.metrics["exported_bounds"] = (
            exported_bounds.model_dump() if exported_bounds else None
        )
        report.metrics["execution_provenance"] = get_execution_provenance()
        return dict(
            status=report.status.value,
            mapping_status=report.mapping_status.value,
            simulation_status=report.simulation_status.value,
            output_complete=manifest.output_complete,
            geometry_package=geometry_package,
            parity_report=report.gates.get(
                "golden_reference_parity", GateResult(status=GateStatus.NOT_RUN)
            ).model_dump(mode="json"),
            fds_text=fds,
            manifest=manifest.model_dump(mode="json"),
            report=report.model_dump(mode="json"),
            markdown_report=report.to_markdown(),
            inventory=compact_inventory(audited),
            mep_graph=audited.mep_graph.model_dump(mode="json"),
            configuration=configuration,
            timings=timings,
        )
