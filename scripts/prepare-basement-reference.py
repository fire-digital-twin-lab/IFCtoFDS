"""Inventory-only research intake; never creates approved ground truth."""

import argparse
import collections
import json
import platform
import subprocess
from pathlib import Path
import ifcopenshell
from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.mep.mep_graph import extract_mep_graph
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.geometry.package import build_package
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.validation.acceptance import AcceptanceReport
from ifc_to_fds.validation.golden import create_candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    model, file = extract_inventory(args.source)
    extract_mep_graph(model, file)
    for e in model.elements:
        e.scope_decision = "UNRESOLVED"
        e.scope_rationale = "Intake only: building/storey selection and geometric relevance require review"
    # Pydantic models use explicit enum values rather than trusting input labels.
    from ifc_to_fds.core.canonical import ScopeDecision

    for e in model.elements:
        e.scope_decision = ScopeDecision.UNRESOLVED
    plan_mapping(model)
    config = dict(profile="research-basement", scope={}, simulation_domain=None)
    package = build_package(model)
    manifest = build_manifest(model, "", config)
    report = AcceptanceReport()
    directory = Path(args.output)
    checksum = create_candidate(directory, model, manifest, package, report, config)
    summary = dict(
        status="DRAFT_INVENTORY_ONLY",
        source_sha256=model.source.source_id,
        original_filename=model.source.filename,
        source_bytes=model.source.file_size_bytes,
        schema=model.source.schema_version,
        unit=model.source.unit_length_name,
        scale=model.source.unit_scale_to_meters,
        products=len(model.elements),
        types=dict(collections.Counter(e.ifc_type for e in model.elements)),
        storeys=[s.model_dump(mode="json") for s in model.storey_references],
        by_building_storey=dict(
            collections.Counter(
                str((e.building_id, e.storey_id)) for e in model.elements
            )
        ),
        type_classes=dict(
            collections.Counter(e.type_class for e in model.elements if e.type_class)
        ),
        categories=dict(
            collections.Counter(
                e.mep_category for e in model.elements if e.classification_evidence
            )
        ),
        systems=len(model.mep_graph.systems),
        ports=len(file.by_type("IfcDistributionPort")),
        source_connection_relations=len(file.by_type("IfcRelConnectsPorts")),
        saved_edges=len(model.mep_graph.connections),
        source_graph_issues=model.mep_graph.issues,
        python=platform.python_version(),
        ifcopenshell=ifcopenshell.version,
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        bundle_sha256=checksum,
        blockers=[
            "SIMULATION_DOMAIN_NOT_APPROVED",
            "SOURCE_GEOMETRY_NOT_PROCESSED",
            "MANUAL_BASELINE_NOT_AVAILABLE",
            "BASEMENT_SCOPE_REVIEW_REQUIRED",
            "BOUNDARY_SOLVER_EVIDENCE_NOT_AVAILABLE",
        ],
    )
    (directory / "intake-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in ("storeys", "by_building_storey", "source_graph_issues")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
