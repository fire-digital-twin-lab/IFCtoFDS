"""MEP graph comparison and audited coverage enrichment.

These checks use the independently re-read model and saved configuration,
never an unverified converter-side graph as the source of truth.
"""

from ifc_to_fds.core.compare import normalize
from ifc_to_fds.domain.validation import GateResult, GateStatus, Finding, Severity


def apply_mep_and_coverage(model, report, configuration) -> None:
    """Preserve MEP mismatch findings and the established coverage dictionary."""
    # MEP audit compares against the saved graph, not the converter object.
    saved = configuration.get("mep_graph")
    if saved is None:
        report.gates["mep"] = GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="No serialized MEP graph supplied",
        )
    elif normalize(saved) != normalize(model.mep_graph.model_dump(mode="json")):
        report.gates["mep"] = GateResult(
            status=GateStatus.FAIL,
            reason="Saved MEP graph differs from IFC source relationships",
        )
        from ifc_to_fds.mep.compare import graph_differences

        differences = graph_differences(
            model.mep_graph.model_dump(mode="json"), saved
        )
        report.gates["mep"].evidence["differences"] = differences
        for difference in differences:
            for key in difference["entities"] or [""]:
                report.findings.append(
                    Finding(
                        id=f"MEP-{len(report.findings) + 1}",
                        severity=Severity.P1,
                        category="mep",
                        title="Saved MEP relationship differs from IFC",
                        detail=str(difference),
                        element_id=key,
                    )
                )
    per_system = {}
    for category in (
        "VENTILATION",
        "SMOKE_EXTRACT",
        "FIRE_SUPPRESSION",
        "PLUMBING",
        "OTHER",
        "UNRESOLVED",
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
            "fds_obstacles": sum(e.fds_representation in ("OBST", "GEOM") for e in members),
            "operational_verified": sum(report.element_statuses.get(e.entity_key) == "OPERATIONAL_MAPPED" for e in members) if report.gates["hvac"].status == GateStatus.PASS else 0,
            "operational_configured": sum(e.operational_status == "CONFIGURED" for e in members),
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
        for decision in (
            "IN_SCOPE",
            "OUT_OF_SCOPE",
            "BOUNDARY_RETAINED",
            "UNRESOLVED",
        )
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
        for role in ("REFERENCE_GEOMETRY", "PASSIVE_OBSTACLE", "OPERATIONAL_MEP", "HVAC")
    }
    report.coverage["boundary_pending"] = [
        e.entity_key
        for e in model.elements
        if e.boundary_treatment == "PENDING_VALIDATION"
    ]

