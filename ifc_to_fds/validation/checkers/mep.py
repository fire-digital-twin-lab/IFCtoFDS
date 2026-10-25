"""MEP systems, network connectivity, and classification validation checker."""

from typing import Any, List, Optional
from ifc_to_fds.core.compare import normalize
from ifc_to_fds.domain.scope.model import ScopeDecision
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, Severity, ValidationContext


class MepChecker:
    name = "mep"

    def __init__(self, expected_mep: Optional[Any] = None):
        self.expected_mep = expected_mep

    def check(self, context: ValidationContext, parsed: Any = None, expected_mep: Optional[Any] = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        if parsed is None or model is None:
            return CheckerOutcome(
                gate_name="mep",
                result=GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="Incomplete diagnostic artifact: FDS text missing",
                ),
                findings=[],
            )
        expected = expected_mep if expected_mep is not None else self.expected_mep
        manifest = context.manifest
        findings: List[Finding] = []
        status = GateStatus.PASS
        reasons = []

        if expected is not None:
            if normalize(model.mep_graph.model_dump()) != normalize(expected.model_dump()):
                status = GateStatus.FAIL
                findings.append(
                    Finding(
                        id=f"FND-{len(findings) + 1:04}",
                        severity=Severity.P1,
                        category="mep",
                        title="MEP graph differs from independently re-read IFC relationships",
                        detail="MEP graph differs from independently re-read IFC relationships",
                    )
                )

        if model.mep_graph.issues:
            for issue in model.mep_graph.issues:
                status = GateStatus.FAIL
                findings.append(
                    Finding(
                        id=f"FND-{len(findings) + 1:04}",
                        severity=Severity.P1,
                        category="mep",
                        title=issue[:100],
                        detail=issue,
                    )
                )

        if any(
            e.classification_evidence
            and e.mep_category in ("OTHER", "UNRESOLVED")
            and e.scope_decision != ScopeDecision.OUT_OF_SCOPE
            for e in model.elements
        ):
            if status != GateStatus.FAIL:
                status = GateStatus.INCONCLUSIVE
            reasons.append("MEP classification is unresolved for one or more source elements")

        if model.mep_graph.isolated_element_ids:
            if status != GateStatus.FAIL:
                status = GateStatus.INCONCLUSIVE
            reasons.append("Isolated MEP elements require source connectivity review")

        if manifest and manifest.schema_version in ("0.4.0", "0.5.0"):
            by_key = {r.entity_key: r for r in manifest.records}
            for e in model.elements:
                key = e.entity_key
                if key in by_key:
                    record = by_key[key]
                    for field in ("ports", "system_ids", "classification_evidence"):
                        expected_value = getattr(e, field)
                        if field == "ports":
                            expected_value = [p.model_dump(mode="json") for p in e.ports]
                        if normalize(getattr(record, field)) != normalize(expected_value):
                            status = GateStatus.FAIL
                            findings.append(
                                Finding(
                                    id=f"FND-{len(findings) + 1:04}",
                                    severity=Severity.P1,
                                    category="mep",
                                    title=f"Manifest {field} differs from independent policy",
                                    detail=f"Manifest {field} differs from independent policy",
                                    element_id=key,
                                )
                            )

        return CheckerOutcome(
            gate_name="mep",
            result=GateResult(status=status, reason="; ".join(reasons)),
            findings=findings,
            metrics={"mep_coverage": model.mep_graph.coverage},
        )
