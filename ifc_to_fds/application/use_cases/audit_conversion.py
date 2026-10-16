"""AuditConversion use case: independent audit of serialized FDS against source IFC."""

from time import perf_counter
from typing import Any, Dict, Optional, Tuple

from ifc_to_fds.core.compare import normalize
from ifc_to_fds.core.federation import load_sources
from ifc_to_fds.domain.bim import BoundingBox, CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest, build_mapping_plan
from ifc_to_fds.domain.scope import SpatialScope
from ifc_to_fds.domain.validation import AcceptanceReport, AuditConfig, GateResult, GateStatus
from ifc_to_fds.geometry.package import audit_package
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.mapping.scope import apply_spatial_scope
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.golden import golden_gate

from ..dto.configuration import validate_configuration


def prepare_model(paths: list[str], configuration: Dict[str, Any], reference: bool = False) -> CanonicalModel:
    """Prepares canonical model with spatial scoping, simulation domain, and mapping plan."""
    configuration = validate_configuration(configuration)
    model = load_sources(paths, configuration.get("sources"), reference=reference)
    scope = SpatialScope.model_validate(configuration.get("scope", {}))
    if scope.storeys or scope.bounding_box:
        apply_spatial_scope(model, scope)
    else:
        model.requested_scope = scope.model_dump(mode="json")
    if configuration.get("simulation_domain"):
        model.simulation_domain = BoundingBox.model_validate(
            configuration["simulation_domain"]
        )
        model.domain_origin = "EXPLICIT_CONFIGURATION"
    elif not scope.storeys and not scope.bounding_box:
        model.simulation_domain = model.model_bounds
        model.domain_origin = "FULL_MODEL"
    plan_mapping(
        model,
        configuration.get("all_geom", False),
        configuration.get("include_review", False),
        configuration.get("decisions", {}),
        configuration.get("boundary_policy"),
    )
    model.mapping_plan = build_mapping_plan(model, cell_size=configuration.get("cell_size", 0.2))
    included = {
        e.entity_key
        for e in model.elements
        if e.scope_decision.value in ("IN_SCOPE", "BOUNDARY_RETAINED")
    }
    for edge in model.mep_graph.connections:
        edge.boundary_connection = (edge.source_element_id in included) != (
            edge.target_element_id in included
        )
    return model


class AuditConversionUseCase:
    """Independent audit use case."""

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
        model = prepare_model(paths, configuration, reference=True)
        config = AuditConfig.model_validate(configuration.get("audit", {}))
        audit_start = perf_counter()
        report = run_independent_validation(model, fds_text, manifest, config)
        validation_done = perf_counter()
        report.requested_level = (
            "simulation" if configuration.get("profile") == "simulation" else "mapping"
        )
        audit_package(model, geometry_package, report, config)
        unplaced = [
            e.entity_key
            for e in model.elements
            if e.role == "PHYSICAL"
            and e.has_3d_geometry
            and e.scope_decision.value != "OUT_OF_SCOPE"
            and e.placement.get("status") != "CONFIRMED"
        ]
        report.gates["placement"] = GateResult(
            status=GateStatus.INCONCLUSIVE if unplaced else GateStatus.PASS,
            reason="Placement missing or unsupported: " + ", ".join(unplaced)
            if unplaced
            else "Source placements re-read and preserved",
        )
        from ifc_to_fds.mapping.boundary import finalize_boundary

        finalize_boundary(model, report, manifest, fds_text, config)
        model_by_key = {e.entity_key: e for e in model.elements}
        for record in manifest.records:
            reference_element = model_by_key.get(record.entity_key)
            if (
                reference_element
                and record.geometry_preservation == "PRESERVED"
                and reference_element.geometry_preservation != "PRESERVED"
            ):
                report.gates["geometry_preservation"] = GateResult(
                    status=GateStatus.FAIL,
                    reason=f"Unsubstantiated preservation claim: {record.entity_key}",
                )
        if manifest.schema_version != "0.5.0":
            report.gates["schema_migration"] = GateResult(
                status=GateStatus.INCONCLUSIVE,
                reason="Legacy artifact requires 0.5 policy review; old VERIFIED is not mapping verification",
            )
        if (
            geometry_package is not None
            and manifest.geometry_package_sha256 != geometry_package.get("sha256")
        ):
            report.gates["geometry_preservation"] = GateResult(
                status=GateStatus.FAIL,
                reason="Manifest geometry package hash differs from saved package",
            )
        if manifest.simulation_domain != (
            model.simulation_domain.model_dump() if model.simulation_domain else None
        ):
            report.gates["domain"] = GateResult(
                status=GateStatus.FAIL,
                reason="Manifest domain differs from independent configuration",
            )
        fields = (
            "source_id",
            "file_hash_sha256",
            "schema_version",
            "unit_scale_to_meters",
            "world_transform",
        )
        actual = {
            s.source_id: {k: s.model_dump()[k] for k in fields} for s in model.sources
        }
        declared = {
            s.get("source_id"): {k: s.get(k) for k in fields} for s in manifest.sources
        }
        if actual == declared:
            if report.gates["source_inventory"].status != GateStatus.FAIL:
                report.gates["source_inventory"] = GateResult(
                    status=GateStatus.PASS,
                    reason="All source hashes and product identities re-read from IFC; per-product reference geometry rebuilt",
                )
        else:
            report.gates["source_inventory"] = GateResult(
                status=GateStatus.FAIL, reason="Source hashes differ from manifest"
            )
        for e in model.elements:
            record = next(
                (r for r in manifest.records if r.entity_key == e.entity_key), None
            )
            if record:
                e.fds_primitive_ids = list(record.fds_primitive_ids)
        # MEP audit compares against the saved graph, not the converter object.
        saved = configuration.get("mep_graph")
        if saved is None:
            report.gates["mep"] = GateResult(
                status=GateStatus.INCONCLUSIVE, reason="No serialized MEP graph supplied"
            )
        elif normalize(saved) != normalize(model.mep_graph.model_dump(mode="json")):
            report.gates["mep"] = GateResult(
                status=GateStatus.FAIL,
                reason="Saved MEP graph differs from IFC source relationships",
            )
        per_system = {}
        for category in (
            "VENTILATION",
            "SMOKE_EXTRACT",
            "FIRE_SUPPRESSION",
            "PLUMBING",
            "OTHER",
        ):
            members = [
                e
                for e in model.elements
                if e.mep_category == category and e.classification_evidence
            ]
            per_system[category] = {
                "reference_geometry": sum(
                    report.element_statuses.get(e.entity_key) == "REFERENCE_PRESERVED"
                    for e in members
                ),
                "fds_obstacles": sum(e.fds_representation != "NONE" for e in members),
                "operational_configured": 0,
                "source_count": len(members),
                "in_scope": sum(
                    e.scope_decision.value in ("IN_SCOPE", "BOUNDARY_RETAINED")
                    for e in members
                ),
                "geometry_verified": sum(
                    report.element_statuses.get(e.entity_key)
                    in ("MATCHED", "REFERENCE_PRESERVED")
                    for e in members
                ),
                "semantic_only": sum(
                    report.element_statuses.get(e.entity_key) == "SEMANTIC_ONLY"
                    for e in members
                ),
                "excluded": sum(
                    report.element_statuses.get(e.entity_key) == "EXCLUDED_APPROVED"
                    for e in members
                ),
                "failed_or_unverified": sum(
                    report.element_statuses.get(e.entity_key)
                    in ("MISSING", "UNSUPPORTED", "DEVIATED", "INCONCLUSIVE")
                    for e in members
                ),
                "ports": sum(len(e.ports) for e in members),
            }
        report.coverage["mep_systems"] = per_system
        report.coverage["scope"] = {
            decision: sum(e.scope_decision.value == decision for e in model.elements)
            for decision in ("IN_SCOPE", "OUT_OF_SCOPE", "BOUNDARY_RETAINED", "UNRESOLVED")
        }
        selectors = model.requested_scope.get("storeys", [])
        report.coverage["scope"]["selected_storeys"] = [
            s.name
            for s in model.storey_references
            if s.storey_id in selectors or s.name in selectors
        ]
        report.configuration["scope"] = model.requested_scope
        report.configuration["simulation_domain"] = (
            model.simulation_domain.model_dump() if model.simulation_domain else None
        )
        report.coverage["representation"] = {
            role: sum(
                e.simulation_role == role and e.scope_decision.value != "OUT_OF_SCOPE"
                for e in model.elements
            )
            for role in ("REFERENCE_GEOMETRY", "PASSIVE_OBSTACLE", "OPERATIONAL_MEP")
        }
        report.coverage["boundary_pending"] = [
            e.entity_key
            for e in model.elements
            if e.boundary_treatment == "PENDING_VALIDATION"
        ]
        parity_start = perf_counter()
        audited_manifest = build_manifest(model, fds_text, configuration, report)
        golden_gate(
            report, model, audited_manifest, geometry_package, configuration, fds_text
        )
        report.metrics["stage_timings"] = dict(
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
        from ifc_to_fds.results import research_context

        report.configuration["research"] = research_context(
            [s.model_dump(mode="json") for s in model.sources],
            configuration,
            report.model_dump(mode="json"),
        )
        report.finalize()
        final = build_manifest(model, fds_text, configuration, report)
        return model, final, report
