"""Assess saved evidence against the independently rebuilt source model.

Order is preserved from the original workflow, including gate overrides.
"""
from ifc_to_fds.domain.validation import GateResult, GateStatus, Finding, Severity
from ifc_to_fds.runtime.normalization import normalize
from ifc_to_fds.modules.geometry.api import audit_package


def assess_saved_evidence(model, fds_text, manifest, configuration, geometry_package, config, report):
    report.requested_level = (
        "simulation" if configuration.get("profile") == "simulation" else "mapping"
    )
    if report.metrics.get("source_topology_preflight_rejected"):
        report.gates["geometry_preservation"] = GateResult(
            status=GateStatus.NOT_RUN,
            reason="Source topology preflight rejected; full package geometry comparison not run",
        )
    else:
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
    from ifc_to_fds.modules.verification.application.boundary_acceptance import finalize_boundary

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
    records_by_key = {r.entity_key: r for r in manifest.records}
    for e in model.elements:
        record = records_by_key.get(e.entity_key)
        if record:
            e.fds_primitive_ids = list(record.fds_primitive_ids)
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
        from ifc_to_fds.modules.bim.api import graph_differences

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
        for role in ("REFERENCE_GEOMETRY", "PASSIVE_OBSTACLE", "OPERATIONAL_MEP")
    }
    report.coverage["boundary_pending"] = [
        e.entity_key
        for e in model.elements
        if e.boundary_treatment == "PENDING_VALIDATION"
    ]

