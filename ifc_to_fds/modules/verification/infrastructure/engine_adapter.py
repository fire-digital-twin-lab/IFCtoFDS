"""Keep the established validation engine authoritative during migration."""

from ifc_to_fds.modules.verification.api import run_independent_validation


class IndependentValidationEngine:
    def __init__(self, solver_runner=None):
        from .fds.solver_process import solver_gates
        self.solver_runner = solver_runner if solver_runner is not None else solver_gates

    def validate(self, model, fds_text, manifest, config):
        return run_independent_validation(model, fds_text, manifest, config, solver_runner=self.solver_runner)
