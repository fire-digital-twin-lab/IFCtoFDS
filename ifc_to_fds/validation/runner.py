"""ValidationRunner orchestrates execution of independent gate checkers."""

from typing import Any, List, Optional
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome, GateChecker
from ifc_to_fds.domain.validation.evaluator import AcceptanceEvaluator
from ifc_to_fds.domain.validation.model import AcceptanceReport, AuditConfig, GateResult, GateStatus, ValidationContext
from ifc_to_fds.validation.parser import parse_fds
from ifc_to_fds.validation.checkers.syntax import FdsSyntaxChecker
from ifc_to_fds.validation.checkers.domain import DomainChecker
from ifc_to_fds.validation.checkers.traceability import TraceabilityChecker
from ifc_to_fds.validation.checkers.scope import ScopeChecker


class ValidationRunner:
    """Orchestrates independent gate checkers against a validation context."""

    def __init__(self, checkers: Optional[List[GateChecker]] = None):
        self.checkers = checkers or self._default_checkers()
        self.evaluator = AcceptanceEvaluator()

    @staticmethod
    def _default_checkers() -> List[GateChecker]:
        return [
            FdsSyntaxChecker(),
            DomainChecker(),
            TraceabilityChecker(),
            ScopeChecker(),
        ]

    def create_context(
        self, model: Any, fds_text: str, manifest: Any = None, config: Optional[AuditConfig] = None
    ) -> ValidationContext:
        config = config or AuditConfig()
        parsed_fds = parse_fds(fds_text) if fds_text else None
        return ValidationContext(
            model=model,
            fds_text=fds_text,
            manifest=manifest,
            config=config,
            parsed_fds=parsed_fds,
        )

    def validate(
        self,
        model: Any,
        fds_text: str,
        manifest: Any = None,
        config: Optional[AuditConfig] = None,
    ) -> AcceptanceReport:
        context = self.create_context(model, fds_text, manifest, config)
        outcomes: List[CheckerOutcome] = []
        for checker in self.checkers:
            outcome = checker.check(context)
            outcomes.append(outcome)
        return self.evaluator.evaluate(context, outcomes)
