"""AuditConversion use case: independent audit of serialized FDS against source IFC."""

from time import perf_counter
from typing import Any, Dict, Optional, Tuple

from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.domain.validation import (
    AcceptanceReport,
    AuditConfig,
    Finding,
    GateResult,
    GateStatus,
    Severity,
)
from ifc_to_fds.geometry.mesh import accepted_source_defects, mesh_digest, mesh_evidence_scope
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
        digests, stale = self._reviewed_defects(model, configuration)
        with accepted_source_defects(digests):
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
        for key in stale:
            report.findings.append(
                Finding(
                    id=f"INC-{len(report.findings) + 1:04}",
                    severity=Severity.P2,
                    category="geometry",
                    title="Accepted source defect no longer matches the model",
                    detail=f"accepted_source_defects[{key}] does not match the current element mesh; it was not applied",
                    element_id=key,
                )
            )
        if stale and report.gates["geometry"].status == GateStatus.PASS:
            report.gates["geometry"].status = GateStatus.INCONCLUSIVE
            report.gates["geometry"].reason = "Stale accepted_source_defects: " + ", ".join(stale)
            report.gates["geometry"].reason_code = "GEOMETRY_INCONCLUSIVE"
        report.finalize()
        report.configuration["research"] = research_context(
            [s.model_dump(mode="json") for s in model.sources],
            configuration,
            report.model_dump(mode="json"),
        )
        final = build_manifest(model, fds_text, configuration, report)
        return model, final, report

    @staticmethod
    def _reviewed_defects(model, configuration):
        """Bind reviewed acceptances to the exact meshes of this audit's own re-read."""
        by_key = {e.entity_key: e for e in model.elements}
        digests, stale = {}, []
        for key, item in (configuration.get("accepted_source_defects") or {}).items():
            element = by_key.get(key)
            if element is not None and element.mesh and mesh_digest(element.mesh) == item["mesh_sha256"]:
                digests[item["mesh_sha256"]] = dict(
                    defect=item["defect"],
                    review={f: item[f] for f in ("policy_version", "reviewer", "rationale", "evidence")},
                )
            else:
                stale.append(key)
        return digests, stale
