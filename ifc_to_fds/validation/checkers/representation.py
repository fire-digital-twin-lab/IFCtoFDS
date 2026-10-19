"""Representation and obstacle authorization validation checker."""

from typing import Any, List
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, Severity, ValidationContext


class RepresentationChecker:
    name = "representation"

    def check(self, context: ValidationContext, parsed: Any = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        findings: List[Finding] = []
        status = GateStatus.PASS
        reasons = []

        known = {e.entity_key: e for e in model.elements} if model else {}

        for p in parsed.primitives:
            key = p.source.get("entity_key", "")
            if key in known:
                e = known[key]
                if e.simulation_role == "REFERENCE_GEOMETRY" or getattr(e, "fds_representation", None) == "NONE":
                    status = GateStatus.FAIL
                    findings.append(
                        Finding(
                            id=f"FND-{len(findings) + 1:04}",
                            severity=Severity.P1,
                            category="representation",
                            title=f"Object without obstacle authorization emitted as {p.id}",
                            detail=f"Object without obstacle authorization emitted as {p.id}",
                            element_id=key,
                        )
                    )
                    reasons.append(f"Object without obstacle authorization emitted: {p.id}")

        return CheckerOutcome(
            gate_name=self.name,
            result=GateResult(
                status=status,
                reason="; ".join(reasons) if reasons else "All emitted primitives have valid obstacle authorization",
            ),
            findings=findings,
        )
