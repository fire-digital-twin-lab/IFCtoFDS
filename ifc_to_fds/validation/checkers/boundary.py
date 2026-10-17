"""Boundary policy and representation validation checker."""

from typing import Dict, List
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, ValidationContext


class BoundaryChecker:
    name = "boundary"

    def check(self, context: ValidationContext) -> CheckerOutcome:
        model = context.model
        findings: List[Finding] = []
        element_statuses: Dict[str, str] = {}
        status = GateStatus.PASS
        reasons = []

        for e in model.elements:
            key = e.entity_key
            if (
                e.boundary_treatment == "PENDING_VALIDATION"
                and e.representation_bounds is None
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
