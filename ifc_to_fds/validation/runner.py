"""ValidationRunner orchestrates execution of independent gate checkers."""

from typing import Any, List, Optional
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome, GateChecker
from ifc_to_fds.domain.validation.evaluator import AcceptanceEvaluator
from ifc_to_fds.domain.validation.model import AcceptanceReport, AuditConfig, GateStatus, ValidationContext
from ifc_to_fds.validation.parser import parse_fds
from ifc_to_fds.validation.checkers.syntax import FdsSyntaxChecker
from ifc_to_fds.validation.checkers.domain import DomainChecker
from ifc_to_fds.validation.checkers.traceability import TraceabilityChecker
from ifc_to_fds.validation.checkers.scope import ScopeChecker
from ifc_to_fds.validation.checkers.geometry import GeometryChecker
from ifc_to_fds.validation.checkers.openings import OpeningsChecker
from ifc_to_fds.validation.checkers.mep import MepChecker
from ifc_to_fds.validation.checkers.boundary import BoundaryChecker
from ifc_to_fds.validation.checkers.solver import SolverChecker


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
            GeometryChecker(),
            OpeningsChecker(),
            MepChecker(),
            BoundaryChecker(),
            SolverChecker(),
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
        syntax_passed = True
        for checker in self.checkers:
            if isinstance(checker, SolverChecker):
                outcome = checker.check(context, syntax_passed=syntax_passed)
            else:
                outcome = checker.check(context)
                if checker.name == "syntax" and outcome.result.status != GateStatus.PASS:
                    syntax_passed = False
            outcomes.append(outcome)
        return self.evaluator.evaluate(context, outcomes)
