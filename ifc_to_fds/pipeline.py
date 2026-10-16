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
from .core.canonical import BoundingBox
from .geometry.package import audit_package
from .validation.golden import golden_gate
from .core.compare import normalize
from .mapping.policy import validate_decisions


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
        "simulation_domain",
        "profile",
        "reference_case",
        "decisions",
        "intentional_deltas",
        "geometry_package_sha256",
        "boundary_policy",
    }
    if unknown:
        raise ValueError(f"Unknown configuration fields: {sorted(unknown)}")
    if config.get("profile", "mapping") not in (
        "mapping",
        "research-basement",
        "simulation",
    ):
        raise ValueError("Unknown acceptance profile")
    if config.get("reference_case") is not None and not isinstance(
        config["reference_case"], str
    ):
        raise ValueError("reference_case must be a case directory or registered ID")
    if config.get("simulation_domain") is not None:
        BoundingBox.model_validate(config["simulation_domain"])
    from .mapping.boundary import POLICY

    if config.get("boundary_policy") not in (None, POLICY):
        raise ValueError("Unsupported boundary policy")
    validate_decisions(config.get("decisions", {}))
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


def audit(paths, fds_text, manifest, configuration=None, geometry_package=None):
    configuration = (
        configuration if configuration is not None else manifest.configuration
    )
    configuration = validate_configuration(configuration)
    if "mep_graph" not in configuration and "mep_graph" in manifest.configuration:
        configuration["mep_graph"] = manifest.configuration["mep_graph"]
    model = prepare(paths, configuration, reference=True)
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
    from .mapping.boundary import finalize_boundary

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
    from .results import research_context

    report.configuration["research"] = research_context(
        [s.model_dump(mode="json") for s in model.sources],
        configuration,
        report.model_dump(mode="json"),
    )
    report.finalize()
    final = build_manifest(model, fds_text, configuration, report)
    return model, final, report


def convert(paths, configuration=None, output_directory=None):
    configuration = validate_configuration(configuration or {})
    start = perf_counter()
    model = prepare(paths, configuration)
    prepared = perf_counter()
    fds, manifest = serialize_fds(model, cell_size=configuration.get("cell_size", 0.2))
    serialized = perf_counter()
    import tempfile
    from .geometry.storage import write_package

    owner = (
        tempfile.TemporaryDirectory(prefix="ifcfds-artifacts-")
        if output_directory is None
        else None
    )
    workspace = Path(owner.name if owner else output_directory)
    workspace.mkdir(parents=True, exist_ok=True)
    geometry_package = write_package(model, workspace / "model_geometry.json", owner)
    (workspace / "model.fds").write_text(fds, encoding="utf-8")
    packaged = perf_counter()
    configuration["geometry_package_sha256"] = geometry_package["sha256"]
    manifest.geometry_package_sha256 = geometry_package["sha256"]
    configuration["mep_graph"] = model.mep_graph.model_dump(mode="json")
    manifest.configuration = configuration
    manifest_path = workspace / "model_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    manifest = MappingManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    fds = (workspace / "model.fds").read_text(encoding="utf-8")
    audited, manifest, report = audit(
        paths, fds, manifest, configuration, geometry_package
    )
    timings = dict(
        **model.timings,
        prepare_s=prepared - start,
        serialize_s=serialized - prepared,
        package_write_s=packaged - serialized,
        **report.metrics.get("stage_timings", {}),
        audit_s=perf_counter() - serialized,
    )
    audited.exported_bounds = model.exported_bounds
    audited.timings = timings
    report.metrics["exported_bounds"] = (
        model.exported_bounds.model_dump() if model.exported_bounds else None
    )
    return dict(
        status=report.status.value,
        mapping_status=report.mapping_status.value,
        simulation_status=report.simulation_status.value,
        output_complete=manifest.output_complete,
        geometry_package=geometry_package,
        parity_report=report.gates["golden_reference_parity"].model_dump(mode="json"),
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
        ("_parity.json", "parity_report"),
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

    from .geometry.storage import copy_package, archive_package, file_hash

    geometry_path = Path(str(base) + "_geometry.json")
    copy_package(result["geometry_package"], geometry_path)
    archive_package(geometry_path, Path(str(base) + "_geometry.zip"))

    checksums = {
        f.name: file_hash(f)
        for f in path.parent.glob(base.name + "*")
        if f.is_file() and not f.name.endswith("_checksums.json")
    }
    Path(str(base) + "_checksums.json").write_text(
        json.dumps(checksums, indent=2), encoding="utf-8"
    )
