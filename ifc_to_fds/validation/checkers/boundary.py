"""Boundary policy and representation validation checker."""

from typing import Any, Dict, List
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, ValidationContext


class BoundaryChecker:
    name = "boundary"

    def check(self, context: ValidationContext, parsed: Any = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        if parsed is None or model is None:
            return CheckerOutcome(
                gate_name="boundary",
                result=GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="Incomplete diagnostic artifact: FDS text missing",
                ),
                findings=[],
            )
        findings: List[Finding] = []
        element_statuses: Dict[str, str] = {}
        status = GateStatus.PASS
        reasons = []

        for e in model.elements:
            key = e.entity_key
            if (
                e.boundary_treatment == "PENDING_VALIDATION"
                and (e.representation_bounds is None
                     or e.boundary_policy == "SOURCE_SOLID_DOMAIN_INTERSECTION")
            ):
                if status != GateStatus.FAIL:
                    status = GateStatus.INCONCLUSIVE
                reasons.append(
                    f"{key}: boundary treatment requires independent solver/effective-geometry evidence"
                )
                element_statuses[key] = "INCONCLUSIVE"

        return CheckerOutcome(
            gate_name="boundary",
            result=GateResult(status=status, reason="; ".join(reasons)),
            findings=findings,
            element_statuses=element_statuses,
        )
