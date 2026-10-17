"""Boundary representations derived from immutable source meshes."""

import hashlib
import json
from pathlib import Path
from ifc_to_fds.core.canonical import BoundingBox
from ifc_to_fds.geometry.mesh import valid_solid, is_axis_aligned_box, box_mesh

POLICY = "VALIDATED_BOUNDARY_OBST_SINGLE_MESH"
EXACT_POLICY = "SOURCE_SOLID_DOMAIN_INTERSECTION"
VERSION = "1.0.0"
FIXTURES = {
    "inside",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
    "zmin",
    "zmax",
    "corner",
    "offgrid",
    "thin",
    "passage",
    "closed_passage",
    "rejected",
}


def adapter_digest():
    mapping_dir = Path(__file__).parent
    validation_dir = Path(__file__).parents[1] / "validation"
    files = [
        mapping_dir / "boundary.py",
        mapping_dir / "policy.py",
        mapping_dir / "exporter.py",
        validation_dir / "effective.py",
        validation_dir / "boundary_fixtures.py",
        validation_dir / "solver.py",
    ]
    return hashlib.sha256(
        "".join(p.read_text(encoding="utf-8") for p in files).encode()
    ).hexdigest()


def eligible_bounds(element, model, force_all_geom=False):
    if (
        force_all_geom
        or model.domain_origin != "EXPLICIT_CONFIGURATION"
        or not model.simulation_domain
        or element.simulation_role != "PASSIVE_OBSTACLE"
        or element.review_status not in ("NOT_REQUIRED", "APPROVED")
        or element.ifc_type.upper()
        not in ("IFCCOLUMN", "IFCWALL", "IFCWALLSTANDARDCASE", "IFCBEAM", "IFCSLAB")
        or element.classification_evidence
        or element.system_ids
        or element.ports
        or element.openings
        or (element.type_class or "")
        .upper()
        .startswith(("IFCDUCT", "IFCPIPE", "IFCFAN", "IFCVALVE"))
        or not element.mesh
        or not valid_solid(element.mesh)
        or not is_axis_aligned_box(element.mesh)
    ):
        return None
    a, b = element.bounding_box.to_xb(), model.simulation_domain.to_xb()
    values = [max(a[i], b[i]) if i % 2 == 0 else min(a[i], b[i]) for i in range(6)]
    if any(values[i + 1] <= values[i] for i in (0, 2, 4)):
        return None
    return BoundingBox(
        **dict(zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), values))
    )


def target_mesh(element):
    if element.boundary_policy == EXACT_POLICY and element.representation_bounds:
        return intersect_solid(element.mesh, element.representation_bounds)
    return (
        box_mesh(element.representation_bounds)
        if element.boundary_policy == POLICY and element.representation_bounds
        else element.mesh
    )


def intersect_solid(mesh, bounds):
    """Intersect actual triangulated solid, including voids, with a domain box."""
    from ifc_to_fds.geometry.boolean import solid_boolean
    from ifc_to_fds.geometry.mesh import as_trimesh
    from ifc_to_fds.core.canonical import TriangleMesh

    solid = solid_boolean(
        [as_trimesh(mesh), as_trimesh(box_mesh(bounds))], "intersection"
    )
    if not solid.is_volume or solid.volume <= 0:
        raise ValueError(
            "Domain intersection has no valid positive-volume source solid"
        )
    return TriangleMesh(vertices=solid.vertices.tolist(), faces=solid.faces.tolist())


def exact_bounds(element, model):
    from ifc_to_fds.geometry.mesh import bounds_for_vertices

    if (
        model.domain_origin != "EXPLICIT_CONFIGURATION"
        or not model.simulation_domain
        or element.simulation_role != "PASSIVE_OBSTACLE"
        or element.review_status not in ("NOT_REQUIRED", "APPROVED")
        or not element.mesh
        or not valid_solid(element.mesh)
    ):
        return None
    # Bounds are measured from the intersected solid, never used as a proxy solid.
    clipped = intersect_solid(element.mesh, model.simulation_domain)
    return bounds_for_vertices(clipped.vertices)


def certificate_valid(path, solver_hash):
    if not path:
        return False, "Boundary solver fixture certificate is missing"
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            spec.get("policy") != POLICY
            or spec.get("policy_version") != VERSION
            or spec.get("solver_sha256") != solver_hash
            or spec.get("solver_version") != "6.11.1"
            or spec.get("adapter_sha256") != adapter_digest()
            or set(spec.get("cases", {})) != FIXTURES
        ):
            return (
                False,
                "Boundary fixture certificate does not cover this policy/solver",
            )
        from .boundary_fixtures_data import fixture_cases, fixture_text
        from ifc_to_fds.validation.effective import effective_obstructions

        for name, case in spec["cases"].items():
            if not case.get("expected_matched"):
                return False, "Unproved solver fixture: " + name
            directory = Path(path).parent / case["directory"]
            run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
            if (
                run.get("sha256") != solver_hash
                or run.get("fds_sha256") != case["fds_sha256"]
            ):
                return False, "Fixture solver/input binding differs"
            for filename, digest in run["files"].items():
                file = (directory / filename).resolve()
                if (
                    file.parent != directory.resolve()
                    or hashlib.sha256(file.read_bytes()).hexdigest() != digest
                ):
                    return False, "Fixture evidence integrity differs"
            text = fixture_text(name, fixture_cases()[name])
            if (directory / "audit.fds").read_bytes() != text.encode():
                return (
                    False,
                    "Fixture input differs from independent definition: " + name,
                )
            if run.get("timed_out") or "6.11.1" not in run.get("reported_versions", []):
                return False, "Fixture did not confirm pinned solver completion"
            if name == "rejected":
                logs = (directory / "stderr.log").read_text(
                    encoding="utf-8", errors="replace"
                )
                logs += (directory / "stdout.log").read_text(
                    encoding="utf-8", errors="replace"
                )
                if "ERROR" not in logs.upper():
                    return False, "Expected solver rejection is missing"
            else:
                outputs = list(directory.glob("*.smv"))
                if run.get("returncode") != 0 or len(outputs) != 1:
                    return False, "Fixture solver output is missing"
                measured = effective_obstructions(
                    text, outputs[0].read_text(encoding="utf-8")
                )
                expected_status = (
                    "FAIL" if name in ("thin", "closed_passage") else "PASS"
                )
                if measured.status != expected_status:
                    return False, "Fixture measurement differs: " + name
        return True, hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return False, "Boundary fixture unavailable: " + str(exc)


def finalize_boundary(model, report, manifest, fds_text, config):
    from ifc_to_fds.validation.acceptance import GateStatus, Finding, Severity

    candidates = [
        e
        for e in model.elements
        if e.boundary_policy == POLICY and e.representation_bounds
    ]
    if not candidates:
        return
    solver, effective = report.gates["solver"], report.gates["effective_geometry"]
    digest = hashlib.sha256(fds_text.encode()).hexdigest()
    valid_certificate, certificate = certificate_valid(
        config.boundary_fixture_certificate, solver.evidence.get("sha256")
    )
    required = (
        "syntax",
        "traceability",
        "scope",
        "domain",
        "geometry",
        "openings",
        "representation",
        "geometry_preservation",
    )
    failures = [
        name
        for name in required
        if name in report.gates and report.gates[name].status == GateStatus.FAIL
    ]
    failed = (
        bool(failures)
        or solver.status == GateStatus.FAIL
        or effective.status == GateStatus.FAIL
    )
    passed = (
        valid_certificate
        and solver.status == GateStatus.PASS
        and effective.status == GateStatus.PASS
        and solver.evidence.get("fds_sha256") == digest
        and effective.evidence.get("fds_sha256") == digest
        and all(
            report.gates.get(name)
            and report.gates[name].status
            in (GateStatus.PASS, GateStatus.NOT_APPLICABLE)
            for name in required
        )
    )
    pending_other = [
        e
        for e in model.elements
        if e.boundary_treatment == "PENDING_VALIDATION" and e not in candidates
    ]
    gate = report.gates["boundary"]
    if failed:
        gate.status = GateStatus.FAIL
        gate.reason = "Boundary geometry/solver evidence failed: " + ", ".join(failures)
    elif passed and not pending_other:
        gate.status = GateStatus.PASS
        gate.reason = "Structural box intersections verified against the exact serialized FDS and pinned solver"
    else:
        gate.status = GateStatus.INCONCLUSIVE
        gate.reason = "Boundary evidence incomplete: " + (
            certificate if not valid_certificate else effective.reason
        )
    for e in candidates:
        if passed:
            e.boundary_treatment = "VALIDATED"
            e.boundary_evidence = dict(
                policy_version=VERSION,
                fds_sha256=digest,
                solver_sha256=solver.evidence["sha256"],
                fixture_sha256=certificate,
                directory=solver.evidence["directory"],
                domain=model.simulation_domain.model_dump(),
                source_id=e.source_id,
                representation_bounds=e.representation_bounds.model_dump(),
            )
        else:
            report.element_statuses[e.entity_key] = (
                "INCONCLUSIVE" if not failed else "DEVIATED"
            )
        claims = next(
            (r for r in manifest.records if r.entity_key == e.entity_key), None
        )
        if failed:
            report.findings.append(
                Finding(
                    id=f"BOUND-{e.entity_key}",
                    severity=Severity.P1,
                    category="boundary",
                    element_id=e.entity_key,
                    title=gate.reason,
                    detail=gate.reason,
                )
            )
        if (
            claims
            and claims.boundary_treatment == "VALIDATED"
            and claims.boundary_evidence.get("fds_sha256") != digest
        ):
            gate.status = GateStatus.FAIL
            report.findings.append(
                Finding(
                    id=f"BOUND-CLAIM-{e.entity_key}",
                    severity=Severity.P1,
                    category="boundary",
                    element_id=e.entity_key,
                    title="Unsubstantiated boundary claim",
                    detail="Saved VALIDATED claim cannot be reproduced",
                )
            )
