"""AuditConversion use case: independent audit of serialized FDS against source IFC."""

from time import perf_counter
from typing import Any, Dict, Optional, Tuple

from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.domain.validation import (
    AcceptanceReport,
    AuditConfig,
    GateResult,
    GateStatus,
)
from ifc_to_fds.geometry.mesh import mesh_evidence_scope
from ifc_to_fds.mapping.manifest import build_manifest
from ..services.audit_integrity import apply_independent_source_integrity
from ..services.audit_mep_coverage import apply_mep_and_coverage
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.golden import golden_gate

from ..dto.configuration import validate_configuration
from ..services.model_preparer import prepare_model

__all__ = ["prepare_model", "AuditConversionUseCase"]


class AuditConversionUseCase:
    """Independent audit use case."""

    @mesh_evidence_scope()
    def execute(
        self,
        paths: list[str],
        fds_text: str,
        manifest: MappingManifest,
        configuration: Optional[Dict[str, Any]] = None,
        geometry_package: Optional[Dict[str, Any]] = None,
    ) -> Tuple[CanonicalModel, MappingManifest, AcceptanceReport]:
        if configuration is None:
            # An artifact can reproduce placement and mapping, but cannot set
            # the tolerance or choose an executable for its own audit.
            manifest_config = manifest.configuration or {}
            configuration = {k: v for k, v in manifest_config.items() if k != "audit"}
        configuration = validate_configuration(configuration)
        manifest_config = manifest.configuration or {}
        if "mep_graph" not in configuration and "mep_graph" in manifest_config:
            configuration["mep_graph"] = manifest_config["mep_graph"]
        source_start = perf_counter()
        model = prepare_model(paths, configuration, reference=True)
        source_done = perf_counter()
        config = AuditConfig.model_validate(configuration.get("audit", {}))
        audit_start = perf_counter()
        report = run_independent_validation(model, fds_text, manifest, config)
        validation_done = perf_counter()
        report.requested_level = (
            "simulation" if configuration.get("profile") == "simulation" else "mapping"
        )
        apply_independent_source_integrity(
            model, fds_text, manifest, geometry_package, report, config
        )
        apply_mep_and_coverage(model, report, configuration)
        parity_start = perf_counter()
        audited_manifest = build_manifest(model, fds_text, configuration, report)
        golden_gate(
            report, model, audited_manifest, geometry_package, configuration, fds_text
        )
        report.metrics["stage_timings"] = dict(
            independent_source_reread_s=source_done - source_start,
            validation_s=validation_done - audit_start,
            package_audit_s=parity_start - validation_done,
            parity_s=perf_counter() - parity_start,
            solver_s=report.metrics.get("solver_s", 0),
        )
        if report.requested_level == "simulation":
            for name in ("physics", "scenario", "operational_model"):
                report.gates[name] = GateResult(
                    status=GateStatus.NOT_RUN,
                    reason="Simulation verification is not implemented by this mapping stage",
                )
        from ifc_to_fds.results import research_context

        # Re-finalize after independent source integrity, MEP and golden
        # reference gates. A research label derived from an earlier verdict
        # must not outlive a later INCONCLUSIVE/REJECTED golden-reference gate.
        report.finalize()
        report.configuration["research"] = research_context(
            [s.model_dump(mode="json") for s in model.sources],
            configuration,
            report.model_dump(mode="json"),
        )
        final = build_manifest(model, fds_text, configuration, report)
        return model, final, report
