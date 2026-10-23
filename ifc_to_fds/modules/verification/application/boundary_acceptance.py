"""Certificate validation and acceptance of boundary representations."""

import hashlib
import json
from pathlib import Path
from ifc_to_fds.modules.simulation.api import POLICY, VERSION, FIXTURES, adapter_digest

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
        from ifc_to_fds.modules.simulation.api import fixture_cases, fixture_text
        from ifc_to_fds.modules.verification.application.effective_obstructions import effective_obstructions

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
    from ifc_to_fds.domain.validation import GateStatus, Finding, Severity

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
