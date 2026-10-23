"""ConvertVerified use case: end-to-end verified BIM-to-FDS conversion."""

import gc
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Union

from ifc_to_fds.domain.mapping import MappingManifest, build_mapping_plan
from ifc_to_fds.modules.artifacts.contracts import CheckpointPayload

from ..dto.configuration import validate_configuration
from .audit_conversion import AuditConversionUseCase
from ..dto.inventory import portable_inventory
from ..ports.conversion import ModelPreparationPort, ConversionWorkspacePort
from ..ports.fds_exporter import FdsExporterPort


class ConvertVerifiedUseCase:
    """Orchestrates verified conversion of IFC models to FDS input."""

    def __init__(self, *, model_preparer: ModelPreparationPort,
                 exporter: FdsExporterPort, workspaces: ConversionWorkspacePort,
                 audit_use_case: AuditConversionUseCase):
        self.model_preparer = model_preparer
        self.exporter = exporter
        self.workspaces = workspaces
        self.audit_use_case = audit_use_case

    def execute(
        self,
        paths: List[str],
        configuration: Optional[Dict[str, Any]] = None,
        output_directory: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        configuration = validate_configuration(configuration or {})
        start = perf_counter()
        model = self.model_preparer.prepare(paths, configuration)
        configuration["rebase_vector"] = model.source.rebase_vector
        prepared = perf_counter()
        cell_size = configuration.get("cell_size", 0.2)
        mapping_plan = build_mapping_plan(model, cell_size=cell_size)
        fds, manifest = self.exporter.serialize_fds(
            model, cell_size=cell_size, mapping_plan=mapping_plan
        )
        serialized = perf_counter()

        workspace = self.workspaces.open(output_directory)
        geometry_package = workspace.write_geometry(model, fds)
        packaged = perf_counter()
        configuration["geometry_package_sha256"] = geometry_package["sha256"]
        manifest.geometry_package_sha256 = geometry_package["sha256"]
        configuration["mep_graph"] = model.mep_graph.model_dump(mode="json")
        manifest.configuration = configuration
        manifest.reseal()
        manifest = workspace.checkpoint(
            CheckpointPayload(portable_inventory(model), configuration["mep_graph"], configuration),
            manifest,
        )
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
        workspace.complete(manifest, report, timings)
        from ifc_to_fds.runtime.provenance import get_execution_provenance

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
            parity_report=report.gates["golden_reference_parity"].model_dump(
                mode="json"
            ),
            fds_text=fds,
            manifest=manifest.model_dump(mode="json"),
            report=report.model_dump(mode="json"),
            markdown_report=report.to_markdown(),
            inventory=portable_inventory(audited),
            mep_graph=audited.mep_graph.model_dump(mode="json"),
            configuration=configuration,
            timings=timings,
        )
