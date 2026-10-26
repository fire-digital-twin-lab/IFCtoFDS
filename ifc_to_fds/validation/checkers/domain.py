"""Simulation domain and computational MESH checker."""

from typing import Any, Dict, List
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, Severity, ValidationContext


class DomainChecker:
    name = "domain"

    def check(self, context: ValidationContext, parsed: Any = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        if parsed is None or model is None:
            return CheckerOutcome(
                gate_name="domain",
                result=GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="Incomplete diagnostic artifact: FDS text missing",
                ),
                findings=[],
            )
        findings: List[Finding] = []
        metrics: Dict[str, Any] = {}
        status = GateStatus.PASS
        reasons = []

        domains = [r.values.get("XB") for r in parsed.records if r.kind == "MESH" and r.values.get("XB")]
        if model.simulation_domain is None:
            status = GateStatus.INCONCLUSIVE
            reasons.append("Explicit simulation domain missing for selected scope")
        elif not domains:
            status = GateStatus.FAIL
            reasons.append("No serialized MESH found in FDS output")
            findings.append(
                Finding(
                    id=f"FND-{len(findings) + 1:04}",
                    severity=Severity.P1,
                    category="domain",
                    title="No serialized MESH found in FDS output",
                    detail="No serialized MESH found in FDS output",
                    element_id="",
                )
            )
        else:
            all_xmin = min(float(d[0]) for d in domains)
            all_xmax = max(float(d[1]) for d in domains)
            all_ymin = min(float(d[2]) for d in domains)
            all_ymax = max(float(d[3]) for d in domains)
            all_zmin = min(float(d[4]) for d in domains)
            all_zmax = max(float(d[5]) for d in domains)
            sim_xb = model.simulation_domain.to_xb()

            diffs = [
                abs(a - b)
                for a, b in zip(
                    (all_xmin, all_xmax, all_ymin, all_ymax, all_zmin, all_zmax),
                    sim_xb,
                )
            ]
            if any(diff > 1e-4 for diff in diffs):
                status = GateStatus.FAIL
                reasons.append(
                    f"Combined MESH bounds [{all_xmin:.4f}, {all_xmax:.4f}, {all_ymin:.4f}, {all_ymax:.4f}, {all_zmin:.4f}, {all_zmax:.4f}] differ from simulation domain {sim_xb}"
                )
                findings.append(
                    Finding(
                        id=f"FND-{len(findings) + 1:04}",
                        severity=Severity.P1,
                        category="domain",
                        title="Serialized MESH bounds differ from declared simulation domain",
                        detail=f"Combined MESH bounds [{all_xmin:.4f}, {all_xmax:.4f}, {all_ymin:.4f}, {all_ymax:.4f}, {all_zmin:.4f}, {all_zmax:.4f}] differ from simulation domain {sim_xb}",
                        element_id="",
                    )
                )
            else:
                mesh_records = [r for r in parsed.records if r.kind == "MESH"]
                metrics["mesh_count"] = len(mesh_records)
                first_mesh = mesh_records[0]
                first_grid = first_mesh.values.get("IJK", [])
                first_xb = first_mesh.values.get("XB", [])
                if (
                    len(first_grid) == 3
                    and all(float(x).is_integer() and x > 0 for x in first_grid)
                    and len(first_xb) == 6
                ):
                    sub_dx = abs(float(first_xb[1]) - float(first_xb[0]))
                    sub_dy = abs(float(first_xb[3]) - float(first_xb[2]))
                    sub_dz = abs(float(first_xb[5]) - float(first_xb[4]))
                    metrics["actual_cell_size_m"] = [
                        sub_dim / n
                        for sub_dim, n in zip(
                            (sub_dx, sub_dy, sub_dz),
                            first_grid,
                        )
                    ]
                else:
                    status = GateStatus.FAIL
                    reasons.append(f"Grid dimensions {first_grid} must be positive integers")
                    findings.append(
                        Finding(
                            id=f"FND-{len(findings) + 1:04}",
                            severity=Severity.P1,
                            category="domain",
                            title="Invalid computational mesh IJK",
                            detail=f"Grid dimensions {first_grid} must be positive integers",
                            element_id="",
                        )
                    )

        return CheckerOutcome(
            gate_name="domain",
            result=GateResult(status=status, reason="; ".join(reasons)),
            findings=findings,
            metrics=metrics,
        )
