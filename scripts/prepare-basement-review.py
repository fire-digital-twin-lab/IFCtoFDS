"""Private new-baseline review pack, with full geometry and unapproved scope."""

import argparse
import collections
import csv
import json
from pathlib import Path
import subprocess
import time
from ifc_to_fds.pipeline import prepare
from ifc_to_fds.geometry.storage import write_package, file_hash
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.validation.acceptance import AcceptanceReport
from ifc_to_fds.validation.golden import create_candidate


def write_boundary_precheck(model, root):
    from ifc_to_fds.geometry.mesh import valid_solid, is_axis_aligned_box

    fields = (
        "entity_key",
        "ifc_type",
        "simulation_role",
        "source_box_candidate",
        "blockers",
        "reviewer",
    )
    with (root / "boundary-precheck.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for e in model.elements:
            if e.scope_decision.value != "BOUNDARY_RETAINED":
                continue
            reasons = []
            if e.ifc_type.upper() not in (
                "IFCCOLUMN",
                "IFCWALL",
                "IFCWALLSTANDARDCASE",
                "IFCBEAM",
                "IFCSLAB",
            ):
                reasons.append("UNSUPPORTED_STRUCTURAL_CLASS")
            if (
                e.simulation_role != "PASSIVE_OBSTACLE"
                or e.classification_evidence
                or e.system_ids
                or e.ports
            ):
                reasons.append("REFERENCE_OR_MEP_OR_UNRESOLVED_ROLE")
            if e.openings:
                reasons.append("SOURCE_OPENINGS")
            if not e.mesh or not valid_solid(e.mesh) or not is_axis_aligned_box(e.mesh):
                reasons.append("NOT_PROVED_CLOSED_AXIS_ALIGNED_BOX")
            if e.review_status not in ("NOT_REQUIRED", "APPROVED"):
                reasons.append("ENTITY_REVIEW_REQUIRED")
            candidate = not reasons
            reasons += [
                "DOMAIN_NOT_APPROVED",
                "DOMAIN_INTERSECTION_NOT_EVALUATED",
                "EXACT_FDS_SOLVER_EVIDENCE_NOT_RUN",
            ]
            writer.writerow(
                dict(
                    entity_key=e.entity_key,
                    ifc_type=e.ifc_type,
                    simulation_role=e.simulation_role,
                    source_box_candidate=candidate,
                    blockers=";".join(reasons),
                    reviewer="",
                )
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(args.source)
    selection = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    if file_hash(source) != selection["source_sha256"]:
        raise ValueError("Source hash differs from candidate intake")
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)

    def progress(stage):
        (root / "progress.json").write_text(
            json.dumps(dict(stage=stage, time=time.time())), encoding="utf-8"
        )

    progress("SOURCE_VERIFIED_GEOMETRY_RUNNING")
    config = dict(
        profile="research-basement",
        scope=dict(storeys=[s["storey_id"] for s in selection["candidate_storeys"]]),
    )
    model = prepare([source], config)
    progress("WRITING_GEOMETRY")
    package = write_package(model, root / "source_geometry.json")
    manifest = build_manifest(model, configuration=config)
    manifest.geometry_package_sha256 = package["sha256"]
    report = AcceptanceReport()
    checksum = create_candidate(
        root / "candidate", model, manifest, package, report, config
    )
    progress("REVIEW_TABLES")
    fields = [
        "entity_key",
        "global_id",
        "ifc_type",
        "name",
        "type_class",
        "building_id",
        "storey_id",
        "scope_decision",
        "geometry_status",
        "mep_category",
        "simulation_role",
        "review_status",
        "system_ids",
        "classification_evidence",
        "bounding_box",
        "reviewer",
        "decision",
    ]
    with (root / "entity-review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for e in model.elements:
            value = e.model_dump(mode="json")
            row = {k: value.get(k, "") for k in fields}
            for k, v in row.items():
                if isinstance(v, (list, dict)):
                    row[k] = json.dumps(v, ensure_ascii=False)
            writer.writerow(row)
    (root / "source_inventory.json").write_text(
        model.model_dump_json(
            exclude={
                "elements": {
                    "__all__": {"mesh": True, "openings": {"__all__": {"mesh": True}}}
                }
            }
        ),
        encoding="utf-8",
    )
    bounds = [
        e.bounding_box
        for e in model.elements
        if e.bounding_box
        and e.scope_decision.value in ("IN_SCOPE", "BOUNDARY_RETAINED")
    ]
    envelope = None
    if bounds:
        envelope = {
            key: fn(getattr(b, key) for b in bounds)
            for key, fn in [
                ("xmin", min),
                ("xmax", max),
                ("ymin", min),
                ("ymax", max),
                ("zmin", min),
                ("zmax", max),
            ]
        }
    (root / "domain-review.json").write_text(
        json.dumps(
            dict(
                status="REVIEW_REQUIRED",
                simulation_domain=None,
                retained_geometry_envelope=envelope,
                warning="Envelope is not a computational domain. Review air-volume boundaries using sections and source documents.",
                candidate_storeys=selection["candidate_storeys"],
                boundary_policy="VALIDATED_BOUNDARY_OBST_SINGLE_MESH",
                boundary_evaluation="NOT_RUN_WITHOUT_APPROVED_DOMAIN",
            ),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Exact triangle/plane intersections, displayed as source sections, not effective FDS.
    import numpy as np

    planes = [("plan-b2", 2, -7.2), ("plan-b1", 2, -2.7)]
    if envelope:
        planes.extend(
            [
                ("section-x", 0, (envelope["xmin"] + envelope["xmax"]) / 2),
                ("section-y", 1, (envelope["ymin"] + envelope["ymax"]) / 2),
            ]
        )
    for name, axis, level in planes:
        segments = []
        other = [i for i in range(3) if i != axis]
        for e in model.elements:
            if not e.mesh or e.scope_decision.value == "OUT_OF_SCOPE":
                continue
            vertices = np.asarray(e.mesh.vertices)
            for face in e.mesh.faces:
                points = vertices[face]
                d = points[:, axis] - level
                hits = []
                for i, j in ((0, 1), (1, 2), (2, 0)):
                    if d[i] * d[j] < 0:
                        hits.append(
                            points[i] + (points[j] - points[i]) * d[i] / (d[i] - d[j])
                        )
                if len(hits) == 2:
                    segments.append((hits[0][other], hits[1][other]))
        if segments:
            allpoints = np.array(segments).reshape(-1, 2)
            lo = allpoints.min(axis=0) - 1
            hi = allpoints.max(axis=0) + 1
            svg = [
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{lo[0]} {lo[1]} {hi[0] - lo[0]} {hi[1] - lo[1]}"><title>DRAFT source section {name}; plane {axis}={level} m; not domain approval</title><g fill="none" stroke="#24547a" stroke-width="0.025">'
            ]
            svg += [f'<path d="M {a[0]} {a[1]} L {b[0]} {b[1]}"/>' for a, b in segments]
            (root / (name + ".svg")).write_text(
                "\n".join(svg + ["</g></svg>"]), encoding="utf-8"
            )
    summary = dict(
        status="DRAFT_NEW_BASELINE",
        origin="NEW_ENGINEER_REVIEW_BASELINE_NOT_HISTORICAL",
        source_sha256=model.source.source_id,
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        tracked_changes=subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"], text=True
        ).splitlines(),
        bundle_sha256=checksum,
        products=len(model.elements),
        geometry=dict(
            collections.Counter(e.geometry_status.value for e in model.elements)
        ),
        scope=dict(collections.Counter(e.scope_decision.value for e in model.elements)),
        blockers=[
            "SCOPE_NOT_APPROVED",
            "DOMAIN_NOT_APPROVED",
            "ENTITY_DECISIONS_NOT_APPROVED",
            "INDEPENDENT_GEOMETRY_AUDIT_NOT_RUN",
            "BOUNDARY_EVIDENCE_PENDING",
            "REFERENCE_NOT_APPROVED",
        ],
    )
    (root / "review-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (root / "README.md").write_text(
        "# New B1/B2 baseline — DRAFT\n\nReview entity-review.csv, source sections and domain-review.json. Section elevations are inspection planes only. Nothing here approves scope, domain, exclusion, classification or historical parity.\n",
        encoding="utf-8",
    )
    write_boundary_precheck(model, root)
    progress("DRAFT_READY")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
