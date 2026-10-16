"""One conversion/audit service for CLI, HTTP and background jobs."""

import json
from pathlib import Path
from time import perf_counter
from .core.federation import load_sources
from .mapping.scope import SpatialScope, apply_spatial_scope
from .mapping.policy import plan_mapping
from .mapping.exporter import serialize_fds
from .mapping.manifest import build_manifest, MappingManifest
from .validation.acceptance import AuditConfig, GateResult, GateStatus
from .validation.engine import run_independent_validation


def validate_configuration(value):
    import copy
    import math

    if not isinstance(value, dict):
        raise ValueError("Configuration must be an object")
    config = copy.deepcopy(value)
    unknown = set(config) - {
        "sources",
        "scope",
        "audit",
        "all_geom",
        "include_review",
        "cell_size",
        "mep_graph",
    }
    if unknown:
        raise ValueError(f"Unknown configuration fields: {sorted(unknown)}")
    SpatialScope.model_validate(config.get("scope", {}))
    AuditConfig.model_validate(config.get("audit", {}))
    sources = config.get("sources", {})
    if not isinstance(sources, dict) or set(sources) - {
        "common_coordinates",
        "transforms",
    }:
        raise ValueError("Invalid source coordinate configuration")
    for key in ("all_geom", "include_review"):
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{key} must be boolean")
    if "common_coordinates" in sources and not isinstance(
        sources["common_coordinates"], bool
    ):
        raise ValueError("common_coordinates must be boolean")
    if "transforms" in sources and not isinstance(sources["transforms"], dict):
        raise ValueError("transforms must be an object")
    cell = float(config.get("cell_size", 0.2))
    if not math.isfinite(cell) or cell <= 0:
        raise ValueError("cell_size must be finite and positive")
    config["cell_size"] = cell
    return config


def prepare(paths, configuration, reference=False):
    configuration = validate_configuration(configuration)
    model = load_sources(paths, configuration.get("sources"), reference=reference)
    scope = SpatialScope.model_validate(configuration.get("scope", {}))
    if scope.storeys or scope.bounding_box:
        apply_spatial_scope(model, scope)
    else:
        model.requested_scope = scope.model_dump(mode="json")
    plan_mapping(
        model,
        configuration.get("all_geom", False),
        configuration.get("include_review", False),
    )
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


def audit(paths, fds_text, manifest, configuration=None):
    configuration = (
        configuration if configuration is not None else manifest.configuration
    )
    configuration = validate_configuration(configuration)
    if "mep_graph" not in configuration and "mep_graph" in manifest.configuration:
        configuration["mep_graph"] = manifest.configuration["mep_graph"]
    model = prepare(paths, configuration, reference=True)
    config = AuditConfig.model_validate(configuration.get("audit", {}))
    report = run_independent_validation(model, fds_text, manifest, config)
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
    elif saved != model.mep_graph.model_dump(mode="json"):
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
            "source_count": len(members),
            "in_scope": sum(
                e.scope_decision.value in ("IN_SCOPE", "BOUNDARY_RETAINED")
                for e in members
            ),
            "geometry_verified": sum(
                report.element_statuses.get(e.entity_key) == "MATCHED" for e in members
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
    report.finalize()
    final = build_manifest(model, fds_text, configuration, report)
    return model, final, report


def convert(paths, configuration=None):
    configuration = validate_configuration(configuration or {})
    start = perf_counter()
    model = prepare(paths, configuration)
    prepared = perf_counter()
    fds, manifest = serialize_fds(model, cell_size=configuration.get("cell_size", 0.2))
    serialized = perf_counter()
    configuration["mep_graph"] = model.mep_graph.model_dump(mode="json")
    manifest.configuration = configuration
    audited, manifest, report = audit(paths, fds, manifest, configuration)
    timings = dict(
        **model.timings,
        prepare_s=prepared - start,
        serialize_s=serialized - prepared,
        audit_s=perf_counter() - serialized,
    )
    audited.exported_bounds = model.exported_bounds
    audited.timings = timings
    report.metrics["exported_bounds"] = (
        model.exported_bounds.model_dump() if model.exported_bounds else None
    )
    return dict(
        status=report.status.value,
        fds_text=fds,
        manifest=manifest.model_dump(mode="json"),
        report=report.model_dump(mode="json"),
        markdown_report=report.to_markdown(),
        inventory=audited.model_dump(
            mode="json",
            exclude={
                "elements": {
                    "__all__": {"mesh": True, "openings": {"__all__": {"mesh": True}}}
                }
            },
        ),
        mep_graph=audited.mep_graph.model_dump(mode="json"),
        configuration=configuration,
        timings=timings,
    )


def save_artifacts(result, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result["fds_text"], encoding="utf-8")
    base = path.with_suffix("")
    for suffix, key in (
        ("_manifest.json", "manifest"),
        ("_acceptance_report.json", "report"),
        ("_inventory.json", "inventory"),
        ("_mep_graph.json", "mep_graph"),
        ("_configuration.json", "configuration"),
        ("_timings.json", "timings"),
    ):
        Path(str(base) + suffix).write_text(
            json.dumps(result[key], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    Path(str(base) + "_manifest.csv").write_text(
        MappingManifest.model_validate(result["manifest"]).to_csv(), encoding="utf-8"
    )
    Path(str(base) + "_acceptance_report.md").write_text(
        result["markdown_report"], encoding="utf-8"
    )
