"""Syntax and namelist grammar checker."""

from typing import Any, List
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, Severity, ValidationContext


class FdsSyntaxChecker:
    name = "syntax"

    def check(self, context: ValidationContext, parsed: Any = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        if parsed is None or model is None:
            return CheckerOutcome(
                gate_name="syntax",
                result=GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="Incomplete diagnostic artifact: FDS text missing",
                ),
                findings=[],
            )
        findings: List[Finding] = []
        status = GateStatus.PASS
        reasons = []

        for error in parsed.errors:
            if error == "Missing MESH" and model.simulation_domain is None:
                if status != GateStatus.FAIL:
                    status = GateStatus.INCONCLUSIVE
                    reasons.append("Incomplete diagnostic artifact: simulation domain is not configured")
            else:
                status = GateStatus.FAIL
                findings.append(
                    Finding(
                        id=f"FND-{len(findings) + 1:04}",
                        severity=Severity.P0,
                        category="syntax",
                        title=error[:100],
                        detail=error,
                        element_id="",
                    )
                )

        for error in parsed.unsupported:
            if status != GateStatus.FAIL:
                status = GateStatus.INCONCLUSIVE
                reasons.append(error)

        reason = "; ".join(reasons)
        return CheckerOutcome(
            gate_name="syntax",
            result=GateResult(status=status, reason=reason),
            findings=findings,
        )
