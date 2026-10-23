"""Solver evidence checker executing NIST FDS dry-run or verification."""

from time import perf_counter
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import GateResult, GateStatus, ValidationContext
from ifc_to_fds.modules.verification.application.engine import solver_gates


class SolverChecker:
    name = "solver"

    def check(self, context: ValidationContext, syntax_passed: bool = True) -> CheckerOutcome:
        fds_text = context.fds_text
        config = context.config

        start = perf_counter()
        if syntax_passed:
            solver_gate, effective_gate = solver_gates(fds_text, config)
        else:
            solver_gate = GateResult(
                status=GateStatus.NOT_RUN, reason="Syntax gate did not pass"
            )
            effective_gate = GateResult(
                status=GateStatus.NOT_RUN, reason="Syntax gate did not pass"
            )

        solver_gate.required = False
        effective_gate.required = False
        elapsed = perf_counter() - start

        return CheckerOutcome(
            gate_name="solver",
            result=solver_gate,
            metrics={"solver_s": elapsed},
        )
