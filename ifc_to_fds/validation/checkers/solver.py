"""Solver evidence checker executing NIST FDS dry-run or verification."""

from time import perf_counter
from typing import Any
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import GateResult, GateStatus, ValidationContext
from ifc_to_fds.validation.solver import solver_gates


class SolverChecker:
    name = "solver"

    def check(
        self,
        context: ValidationContext,
        parsed: Any = None,
        syntax_passed: bool = True,
        mesh_passed: bool = True,
    ) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        if parsed is None or model is None:
            return CheckerOutcome(
                gate_name="solver",
                result=GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="Incomplete diagnostic artifact: FDS text missing",
                ),
                findings=[],
            )
        fds_text = context.fds_text
        config = context.config

        start = perf_counter()
        if not syntax_passed:
            solver_gate = GateResult(
                status=GateStatus.NOT_RUN, reason="Syntax gate did not pass"
            )
            effective_gate = GateResult(
                status=GateStatus.NOT_RUN, reason="Syntax gate did not pass"
            )
        else:
            # Solver integration evidence is independent from scientific mesh
            # adequacy. An INCONCLUSIVE mesh gate must not suppress an otherwise
            # executable pinned-FDS run; the acceptance model keeps mesh and
            # solver verdicts separate, so solver PASS cannot upgrade mesh adequacy.
            solver_gate, effective_gate = solver_gates(fds_text, config)
            if not mesh_passed:
                solver_gate.evidence["mesh_adequacy_status"] = "INCONCLUSIVE"
                solver_gate.evidence[
                    "mesh_adequacy_note"
                ] = "Solver execution does not establish grid adequacy"
                effective_gate.evidence["mesh_adequacy_status"] = "INCONCLUSIVE"

        solver_gate.required = False
        effective_gate.required = False
        elapsed = perf_counter() - start

        return CheckerOutcome(
            gate_name="solver",
            result=solver_gate,
            metrics={
                "solver_s": elapsed,
                "mesh_adequacy_passed": mesh_passed,
            },
            additional_gates={"effective_geometry": effective_gate},
        )
