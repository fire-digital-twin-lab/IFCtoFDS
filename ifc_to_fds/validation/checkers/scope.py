"""Spatial scope validation checker."""

from typing import Any, Dict, List
from ifc_to_fds.domain.scope.model import ScopeDecision
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, Severity, ValidationContext


class ScopeChecker:
    name = "scope"

    def check(self, context: ValidationContext, parsed: Any = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        findings: List[Finding] = []
        element_statuses: Dict[str, str] = {}
        status = GateStatus.PASS
        reasons = []

        emitted_keys = {
            p.source.get("entity_key")
            for p in parsed.primitives
            if p.source.get("entity_key")
        }

        for e in model.elements:
            key = e.entity_key
            if e.scope_decision == ScopeDecision.OUT_OF_SCOPE:
                if key in emitted_keys:
                    status = GateStatus.FAIL
                    findings.append(
                        Finding(
                            id=f"FND-{len(findings) + 1:04}",
                            severity=Severity.P0,
                            category="scope",
                            title=f"Out-of-scope element exported as primitive: {key}",
                            detail=f"Out-of-scope element exported: {key}",
                            element_id=key,
                        )
                    )
            elif e.scope_decision == ScopeDecision.UNRESOLVED:
                if status != GateStatus.FAIL:
                    status = GateStatus.INCONCLUSIVE
                reasons.append(f"Unresolved element {key}")
                element_statuses[key] = "INCONCLUSIVE"
                if key in emitted_keys:
                    status = GateStatus.FAIL
                    findings.append(
                        Finding(
                            id=f"FND-{len(findings) + 1:04}",
                            severity=Severity.P1,
                            category="scope",
                            title=f"Unresolved-scope element was emitted: {key}",
                            detail=f"Unresolved-scope element was emitted: {key}",
                            element_id=key,
                        )
                    )

        return CheckerOutcome(
            gate_name="scope",
            result=GateResult(status=status, reason="; ".join(reasons)),
            findings=findings,
            element_statuses=element_statuses,
        )
