"""Simulation domain and computational MESH checker."""

from typing import Any, Dict, List
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, Severity, ValidationContext


class DomainChecker:
    name = "domain"

    def check(self, context: ValidationContext, parsed: Any = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        findings: List[Finding] = []
        metrics: Dict[str, Any] = {}
        status = GateStatus.PASS
        reasons = []

        domains = [r.values.get("XB") for r in parsed.records if r.kind == "MESH"]
        if model.simulation_domain is None:
            status = GateStatus.INCONCLUSIVE
            reasons.append("Explicit simulation domain missing for selected scope")
        elif len(domains) != 1 or any(
            abs(float(a) - b) > 1e-8
            for a, b in zip(domains[0], model.simulation_domain.to_xb())
        ):
            status = GateStatus.FAIL
            findings.append(
                Finding(
                    id=f"FND-{len(findings) + 1:04}",
                    severity=Severity.P1,
                    category="domain",
                    title="Serialized MESH differs from declared simulation domain",
                    detail="Serialized MESH differs from declared simulation domain",
                    element_id="",
                )
            )
        else:
            mesh_record = next(r for r in parsed.records if r.kind == "MESH")
            grid = mesh_record.values.get("IJK", [])
            if len(grid) == 3 and all(float(x).is_integer() and x > 0 for x in grid):
                metrics["actual_cell_size_m"] = [
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
                status = GateStatus.FAIL
                findings.append(
                    Finding(
                        id=f"FND-{len(findings) + 1:04}",
                        severity=Severity.P1,
                        category="domain",
                        title="Invalid computational mesh IJK",
                        detail="Invalid computational mesh IJK",
                        element_id="",
                    )
                )

        return CheckerOutcome(
            gate_name="domain",
            result=GateResult(status=status, reason="; ".join(reasons)),
            findings=findings,
            metrics=metrics,
        )
