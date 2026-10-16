"""Read serialized FDS and verify against a separate source reference model."""

import hashlib
from .acceptance import (
    AcceptanceReport,
    AuditConfig,
    Finding,
    GateResult,
    GateStatus,
    Severity,
)
from .parser import parse_fds
from .metrics import compare_solids, opening_residual, passage_metrics
from .solver import solver_gates
from ifc_to_fds.core.compare import normalize
from ifc_to_fds.core.canonical import MappingStrategy, ScopeDecision
from ifc_to_fds.geometry.mesh import valid_solid, as_trimesh, bounds_for_vertices


def parse_serialized_fds_primitives(text):
    return {r.id: r for r in parse_fds(text).primitives}


def run_independent_validation(
    model, fds_text, manifest=None, config=None, expected_mep=None
):
    config = config or AuditConfig()
    report = AcceptanceReport(
        total_elements_checked=len(model.elements), configuration=config.model_dump()
    )
    report.gates = {
        name: GateResult(status=GateStatus.PASS)
        for name in (
            "syntax",
            "source_inventory",
            "traceability",
            "scope",
            "geometry",
            "openings",
            "mep",
            "representation",
            "boundary",
            "domain",
        )
    }
    report.gates["source_inventory"] = GateResult(
        status=GateStatus.INCONCLUSIVE,
        reason="Reference model supplied in memory; source inventory has not been independently re-read",
    )

    def finding(gate, detail, key="", severity=Severity.P1):
        report.gates[gate].status = GateStatus.FAIL
        report.findings.append(
            Finding(
                id=f"FND-{len(report.findings) + 1:04}",
                severity=severity,
                category=gate,
                title=detail[:100],
                detail=detail,
                element_id=key,
            )
        )

    def unknown(gate, reason):
        if report.gates[gate].status != GateStatus.FAIL:
            report.gates[gate].status = GateStatus.INCONCLUSIVE
            report.gates[gate].reason += reason + "; "

    parsed = parse_fds(fds_text)
    for error in parsed.errors:
        if error == "Missing MESH" and model.simulation_domain is None:
            unknown(
                "syntax",
                "Incomplete diagnostic artifact: simulation domain is not configured",
            )
        else:
            finding("syntax", error, severity=Severity.P0)
    for error in parsed.unsupported:
        unknown("syntax", error)
    records = manifest.records if manifest else []
    by_key = {r.entity_key: r for r in records}
    primitives = {}
    actual_ids = set()
    known = {e.entity_key: e for e in model.elements}
    domains = [r.values.get("XB") for r in parsed.records if r.kind == "MESH"]
    if len(domains) != 1:
        unknown(
            "geometry",
            "Multiple computational meshes need an explicit domain-union audit",
        )
    if model.simulation_domain is None:
        unknown("domain", "Explicit simulation domain missing for selected scope")
    elif len(domains) != 1 or any(
        abs(float(a) - b) > 1e-8
        for a, b in zip(domains[0], model.simulation_domain.to_xb())
    ):
        finding("domain", "Serialized MESH differs from declared simulation domain")
    else:
        mesh_record = next(r for r in parsed.records if r.kind == "MESH")
        grid = mesh_record.values.get("IJK", [])
        if len(grid) == 3 and all(float(x).is_integer() and x > 0 for x in grid):
            report.metrics["actual_cell_size_m"] = [
                d / n
                for d, n in zip(
                    (
                        model.simulation_domain.dx,
                        model.simulation_domain.dy,
                        model.simulation_domain.dz,
                    ),
                    grid,
                )
            ]
        else:
            finding("domain", "Invalid computational mesh IJK")
    for p in parsed.primitives:
        actual_ids.add(p.id)
        key = p.source.get("entity_key", "")
        if not key and p.source.get("legacy"):
            candidates = [
                e
                for e in model.elements
                if e.global_id == p.source.get("global_id")
                and e.step_id == p.source.get("step_id")
            ]
            if len(candidates) == 1:
                key = candidates[0].entity_key
                unknown(
                    "traceability", f"Legacy source metadata lacks file hash: {p.id}"
                )
        if key not in known:
            finding(
                "traceability",
                f"Unexpected primitive {p.id}: source entity {key!r} is not in inventory",
                key,
                Severity.P0,
            )
            continue
        e = known[key]
        if (
            p.source.get("global_id") != e.global_id
            or p.source.get("step_id") != e.step_id
            or (not p.source.get("legacy") and p.source.get("source_id") != e.source_id)
        ):
            finding("traceability", f"Conflicting provenance for primitive {p.id}", key)
        if e.scope_decision == ScopeDecision.OUT_OF_SCOPE:
            finding(
                "scope", f"Out-of-scope element exported as {p.id}", key, Severity.P0
            )
        if e.simulation_role == "REFERENCE_GEOMETRY" or e.fds_representation == "NONE":
            finding(
                "representation",
                f"Object without obstacle authorization emitted as {p.id}",
                key,
            )
        if e.role != "PHYSICAL":
            finding("traceability", f"Nonphysical entity emitted as solid: {p.id}", key)
        if p.kind in ("OBST", "GEOM"):
            try:
                solid = p.mesh()
                bounds = bounds_for_vertices(solid.vertices)
                if bounds and len(domains) == 1:
                    xb = domains[0]
                    coordinates = bounds.to_xb()
                    if any(
                        coordinates[i] < xb[i] - 1e-6
                        if i % 2 == 0
                        else coordinates[i] > xb[i] + 1e-6
                        for i in range(6)
                    ):
                        finding(
                            "geometry",
                            f"Primitive outside computational mesh: {p.id}",
                            key,
                        )
                primitives.setdefault(key, []).append(solid)
            except ValueError as exc:
                finding("syntax", str(exc), key)
        else:
            unknown("geometry", f"{p.kind} effective semantics not supported")
    if manifest:
        if manifest.fds_sha256 != hashlib.sha256(fds_text.encode()).hexdigest():
            finding(
                "traceability",
                "Serialized FDS hash differs from manifest",
                severity=Severity.P0,
            )
        if len(by_key) != len(records) or set(by_key) != set(known):
            finding(
                "source_inventory",
                "Manifest entity inventory differs from source",
                severity=Severity.P0,
            )
        manifest_ids = {p for r in records for p in r.fds_primitive_ids}
        if manifest_ids != actual_ids:
            finding(
                "traceability",
                "Manifest primitive set differs from serialized FDS",
                severity=Severity.P0,
            )
        reverse = {}
        for r in records:
            for pid in r.fds_primitive_ids:
                reverse.setdefault(pid, []).append(r.entity_key)
        if reverse != manifest.primitive_to_ifc:
            finding("traceability", "Manifest reverse mapping conflicts with records")
        for p in parsed.primitives:
            if p.id not in reverse or p.source.get("entity_key") not in reverse[p.id]:
                finding(
                    "traceability",
                    f"Primitive {p.id} disagrees with manifest source mapping",
                )
    else:
        unknown("traceability", "No manifest supplied")
    opening_count = 0
    for e in model.elements:
        key = e.entity_key
        if e.scope_decision == ScopeDecision.UNRESOLVED:
            unknown("scope", f"Unresolved element {key}")
            report.element_statuses[key] = "INCONCLUSIVE"
            if key in primitives:
                finding("scope", "Unresolved-scope element was emitted", key)
            continue
        strategy = (
            by_key[key].mapping_strategy if key in by_key else e.mapping_strategy.value
        )
        # Do not trust a manifest that silently changes the independently planned disposition.
        if key in by_key:
            r = by_key[key]
            if (
                r.global_id,
                r.step_id,
                r.source_id,
                r.mapping_strategy,
                r.scope_decision,
            ) != (
                e.global_id,
                e.step_id,
                e.source_id,
                e.mapping_strategy.value,
                e.scope_decision.value,
            ):
                finding(
                    "traceability",
                    "Manifest decision/provenance differs from source policy",
                    key,
                )
        if key in by_key and manifest.schema_version == "0.5.0":
            record = by_key[key]
            expected_bounds = (
                e.representation_bounds.model_dump()
                if e.representation_bounds
                else None
            )
            if (
                record.boundary_policy != e.boundary_policy
                or record.representation_bounds != expected_bounds
                or record.placement != e.placement
                or record.source_bounds
                != (e.bounding_box.model_dump() if e.bounding_box else None)
            ):
                finding(
                    "representation",
                    "Boundary plan or placement differs from independent IFC policy",
                    key,
                )
        if key in by_key and manifest.schema_version in ("0.4.0", "0.5.0"):
            record = by_key[key]
            for field in (
                "source_presence",
                "simulation_role",
                "operational_status",
                "fds_representation",
                "review_status",
                "decision",
                "system_ids",
                "classification_evidence",
                "ports",
                "openings",
            ):
                expected_value = getattr(e, field)
                if field == "ports":
                    expected_value = [p.model_dump(mode="json") for p in e.ports]
                elif field == "openings":
                    expected_value = [
                        o.model_dump(
                            mode="json",
                            exclude={
                                "mesh",
                                "bounding_box",
                                "is_subtracted",
                                "verification_status",
                            },
                        )
                        for o in e.openings
                    ]
                if normalize(getattr(record, field)) != normalize(expected_value):
                    finding(
                        "representation",
                        f"Manifest {field} differs from independent policy",
                        key,
                    )
        if (
            e.review_status == "REVIEW_REQUIRED"
            and e.scope_decision != ScopeDecision.OUT_OF_SCOPE
        ):
            unknown("representation", f"Review decision required for {key}")
        if (
            e.boundary_treatment == "PENDING_VALIDATION"
            and e.representation_bounds is None
        ):
            unknown(
                "boundary",
                f"{key}: boundary treatment requires independent solver/effective-geometry evidence",
            )
            report.element_statuses[key] = "INCONCLUSIVE"
        if strategy == MappingStrategy.EXCLUDED_SCOPE.value:
            report.excluded_count += 1
            report.element_statuses[key] = "EXCLUDED_SCOPE"
            if key in primitives:
                finding("scope", "Scope-excluded element emitted", key)
            continue
        if strategy == MappingStrategy.EXCLUDED_APPROVED.value:
            report.excluded_count += 1
            report.element_statuses[key] = "EXCLUDED_APPROVED"
            if key in primitives:
                finding("scope", "Excluded element has emitted geometry", key)
            continue
        if strategy == MappingStrategy.SEMANTIC_ONLY.value:
            report.semantic_only_count += 1
            report.element_statuses[key] = "SEMANTIC_ONLY"
            if key in primitives:
                finding(
                    "traceability", "Semantic-only element emitted as geometry", key
                )
            continue
        if strategy == MappingStrategy.NONE.value:
            report.element_statuses[key] = (
                "REVIEW_REQUIRED"
                if e.review_status == "REVIEW_REQUIRED"
                else "INCONCLUSIVE"
            )
            continue
        meshes = primitives.get(key, [])
        if not meshes:
            report.missing_count += 1
            report.element_statuses[key] = "MISSING"
            finding(
                "traceability",
                f"Missing required FDS solid: {e.global_id}",
                key,
                Severity.P0,
            )
            continue
        if not e.mesh or not valid_solid(e.mesh):
            report.element_statuses[key] = "UNSUPPORTED"
            finding(
                "geometry",
                f"Source physical solid missing or invalid: {e.global_id}",
                key,
            )
            continue
        try:
            from ifc_to_fds.mapping.boundary import target_mesh

            metrics = compare_solids(target_mesh(e), meshes)
            report.metrics[key] = metrics
            fail = (
                metrics["surface_distance_m"] > config.surface_tolerance_m
                or metrics["relative_volume_error"] > config.relative_volume_tolerance
                or metrics["solid_iou"] < config.min_solid_iou
                or metrics["reference_components"] != metrics["output_components"]
            )
            if fail:
                finding("geometry", f"Geometric deviation: {metrics}", key)
                report.deviated_count += 1
                report.element_statuses[key] = "DEVIATED"
            elif not metrics["surface_proven"]:
                unknown("geometry", f"Full surface distance not proven for {key}")
                report.element_statuses[key] = "INCONCLUSIVE"
            else:
                report.matched_count += 1
                report.element_statuses[key] = "MATCHED"
        except ValueError as exc:
            finding("geometry", f"{key}: invalid solid comparison: {exc}", key)
            report.element_statuses[key] = "DEVIATED"
        except Exception as exc:
            unknown("geometry", f"{key}: solid comparison failed: {exc}")
            report.element_statuses[key] = "INCONCLUSIVE"
        for opening in e.openings:
            opening_count += 1
            try:
                source_residual = opening_residual([e.mesh], opening.mesh)
                output_residual = opening_residual(meshes, opening.mesh)
                opening_solid = as_trimesh(opening.mesh)
                opening_tolerance = max(
                    1e-6,
                    config.surface_tolerance_m
                    * opening_solid.area
                    / max(opening_solid.volume, 1e-12),
                )
                if source_residual > opening_tolerance:
                    unknown(
                        "openings",
                        f"Source opening subtraction not proven: {opening.opening_global_id}",
                    )
                elif output_residual > opening_tolerance:
                    finding(
                        "openings",
                        f"Opening blocked in emitted host: {opening.opening_global_id}",
                        key,
                    )
                reference_solids = [
                    x.mesh
                    for x in model.elements
                    if x.mesh
                    and x.role == "PHYSICAL"
                    and x.mapping_strategy
                    in (MappingStrategy.OBST, MappingStrategy.GEOM)
                    and x.scope_decision
                    in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
                ]
                exported_solids = [
                    mesh for group in primitives.values() for mesh in group
                ]
                passage = passage_metrics(
                    reference_solids, exported_solids, opening.mesh
                )
                if (
                    passage["normalized_symmetric_difference"] > opening_tolerance
                    or passage["source_free_components"]
                    != passage["output_free_components"]
                ):
                    finding(
                        "openings",
                        f"Opening passage changed, including fills/blockers: {opening.opening_global_id}",
                        key,
                    )
                report.metrics.setdefault(key, {})[
                    f"opening:{opening.opening_global_id}"
                ] = dict(
                    source_residual=source_residual,
                    output_residual=output_residual,
                    passage=passage,
                )
            except Exception as exc:
                unknown("openings", f"{opening.opening_global_id}: {exc}")
    if not opening_count:
        report.gates["openings"] = GateResult(
            status=GateStatus.NOT_APPLICABLE,
            reason="No mapped host has source openings",
        )
    if expected_mep is not None:
        if normalize(model.mep_graph.model_dump()) != normalize(
            expected_mep.model_dump()
        ):
            finding(
                "mep", "MEP graph differs from independently re-read IFC relationships"
            )
    if model.mep_graph.issues:
        for issue in model.mep_graph.issues:
            finding("mep", issue)
    if any(
        e.classification_evidence and e.mep_category == "OTHER" for e in model.elements
    ):
        unknown(
            "mep", "MEP classification is unresolved for one or more source elements"
        )
    if model.mep_graph.isolated_element_ids:
        unknown("mep", "Isolated MEP elements require source connectivity review")
    report.coverage = dict(
        inventory=len(model.elements),
        geometry=report.matched_count,
        missing=report.missing_count,
        openings=opening_count,
        mep=model.mep_graph.coverage,
    )
    from time import perf_counter

    solver_start = perf_counter()
    if report.gates["syntax"].status == GateStatus.PASS:
        report.gates["solver"], report.gates["effective_geometry"] = solver_gates(
            fds_text, config
        )
    else:
        report.gates["solver"] = GateResult(
            status=GateStatus.NOT_RUN, reason="Syntax gate did not pass"
        )
        report.gates["effective_geometry"] = GateResult(
            status=GateStatus.NOT_RUN, reason="Syntax gate did not pass"
        )
    report.metrics["solver_s"] = perf_counter() - solver_start
    report.gates["solver"].required = False
    report.gates["effective_geometry"].required = False
    return report.finalize()
