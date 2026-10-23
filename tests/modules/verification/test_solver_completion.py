"""Completion must prove time advancement, without mistaking residuals for errors."""

import sys

import pytest

from ifc_to_fds.domain.validation import AuditConfig
from ifc_to_fds.modules.verification.api import solver_gates
from tests.support.solver_cases import solver_cases


def run_output(monkeypatch, tmp_path, output, end=1, code=0):
    import ifc_to_fds.modules.verification.infrastructure.fds.solver_process as adapter

    class Process:
        def __init__(self, command, **kwargs):
            self.probe = len(command) == 1
            self.returncode = code

        def communicate(self, timeout=None):
            if self.probe:
                return b"FDS-6.11.1", None
            return output.encode(), b""

    monkeypatch.setattr(adapter.platform, "platform", lambda: "fixture-platform")
    monkeypatch.setattr(adapter.subprocess, "Popen", Process)
    text = solver_cases()["obst"].replace("T_END=0", f"T_END={end}")
    return solver_gates(
        text,
        AuditConfig(
            solver_executable=sys.executable,
            solver_evidence_directory=str(tmp_path),
        ),
    )[0]


def test_numerical_residual_is_not_a_fatal_solver_error(monkeypatch, tmp_path):
    gate = run_output(
        monkeypatch,
        tmp_path,
        "Time Step: 5, Simulation Time: 1.00000 s\n"
        "Maximum Pressure Error: 0.38E-05 on Mesh 1\n"
        "Maximum Velocity Error: 0.00E+00 on Mesh 1\n"
        "STOP: FDS completed successfully (CHID: acceptance)\n",
    )
    assert gate.status == "PASS", gate.reason


@pytest.mark.parametrize(
    "output",
    [
        "STOP: Set-up only (CHID: acceptance)",
        "STOP: FDS completed successfully (CHID: acceptance)",
        "Time Step: 1, Simulation Time: 0.2 s\nSTOP: FDS completed successfully",
    ],
)
def test_positive_end_time_requires_observed_time_advancement(
    monkeypatch, tmp_path, output
):
    assert run_output(monkeypatch, tmp_path, output).status != "PASS"


@pytest.mark.parametrize(
    "error", ["ERROR: bad input", "ERROR(426): Poisson initialization error: 1"]
)
def test_actual_fatal_diagnostic_cannot_be_overridden_by_success(
    monkeypatch, tmp_path, error
):
    gate = run_output(
        monkeypatch,
        tmp_path,
        f"{error}\nTime Step: 5, Simulation Time: 1.0 s\nSTOP: FDS completed successfully",
    )
    assert gate.status == "FAIL"
