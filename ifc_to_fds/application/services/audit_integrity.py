"""Post-engine integrity checks against independently reconstructed IFC evidence.

Scientific gates and report mutation order were extracted verbatim from the
original AuditConversionUseCase. This module never reruns source parsing.
"""

from ifc_to_fds.domain.validation import GateResult, GateStatus
from ifc_to_fds.geometry.package import audit_package


def apply_independent_source_integrity(
    model, fds_text, manifest, geometry_package, report, config
) -> None:
    """Recheck geometry, placement, provenance, domain and primitive identities."""
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
        if report.gates.get("source_inventory", GateResult(status=GateStatus.NOT_RUN)).status != GateStatus.FAIL:
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

