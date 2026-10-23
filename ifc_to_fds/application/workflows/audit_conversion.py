"""AuditConversion use case: independent audit of serialized FDS against source IFC."""

from time import perf_counter
from typing import Any, Dict, Optional, Tuple

from ifc_to_fds.runtime.normalization import normalize
from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.domain.validation import (
    AcceptanceReport,
    AuditConfig,
    GateResult,
    GateStatus,
)
from ifc_to_fds.domain.validation import Finding, Severity
from ifc_to_fds.modules.geometry.api import audit_package
from ifc_to_fds.modules.geometry.api import mesh_evidence_scope
from ifc_to_fds.modules.fds.api import build_manifest
from ifc_to_fds.modules.reference.api import golden_gate

from ..dto.configuration import validate_configuration
from ..ports.conversion import ModelPreparationPort, ValidationEnginePort
from .prepare_model import prepare_model

__all__ = ["prepare_model", "AuditConversionUseCase"]


class AuditConversionUseCase:
    """Independent audit use case."""

    def __init__(self, *, model_preparer: ModelPreparationPort, validation_engine: ValidationEnginePort, reference_reader=None):
        self.model_preparer = model_preparer
        self.validation_engine = validation_engine
        self.reference_reader = reference_reader

    @mesh_evidence_scope()
    def execute(
        self,
        paths: list[str],
        fds_text: str,
        manifest: MappingManifest,
        configuration: Optional[Dict[str, Any]] = None,
        geometry_package: Optional[Dict[str, Any]] = None,
    ) -> Tuple[CanonicalModel, MappingManifest, AcceptanceReport]:
        configuration = (
            configuration if configuration is not None else manifest.configuration
        )
        configuration = validate_configuration(configuration)
        if "mep_graph" not in configuration and "mep_graph" in manifest.configuration:
            configuration["mep_graph"] = manifest.configuration["mep_graph"]
        source_start = perf_counter()
        model = self.model_preparer.prepare(paths, configuration, reference=True)
        source_done = perf_counter()
        config = AuditConfig.model_validate(configuration.get("audit", {}))
        audit_start = perf_counter()
        report = self.validation_engine.validate(model, fds_text, manifest, config)
        validation_done = perf_counter()
        from ifc_to_fds.modules.verification.api import assess_saved_evidence

        assess_saved_evidence(model, fds_text, manifest, configuration, geometry_package, config, report)
        parity_start = perf_counter()
        audited_manifest = build_manifest(model, fds_text, configuration, report)
        golden_gate(
            report, model, audited_manifest, geometry_package, configuration, fds_text,
            case_reader=self.reference_reader,
        )
        report.metrics["stage_timings"] = dict(
            independent_source_reread_s=source_done - source_start,
            validation_s=validation_done - audit_start,
            package_audit_s=parity_start - validation_done,
            parity_s=perf_counter() - parity_start,
            solver_s=report.metrics.get("solver_s", 0),
        )
        if report.requested_level == "simulation":
            for name in ("physics", "scenario", "mesh_resolution", "operational_model"):
                report.gates[name] = GateResult(
                    status=GateStatus.NOT_RUN,
                    reason="Simulation verification is not implemented by this mapping stage",
                )
        report.finalize()
        from ifc_to_fds.modules.reference.api import research_context

        report.configuration["research"] = research_context(
            [s.model_dump(mode="json") for s in model.sources],
            configuration,
            report.model_dump(mode="json"),
        )
        report.finalize()
        final = build_manifest(model, fds_text, configuration, report)
        return model, final, report
