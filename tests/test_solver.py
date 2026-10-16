import os
from pathlib import Path
import shutil
import pytest
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation.acceptance import AuditConfig
from ifc_to_fds.validation.solver import solver_gates


def test_missing_solver_never_passes(box_model, monkeypatch):
    monkeypatch.setattr("ifc_to_fds.validation.solver.shutil.which", lambda _: None)
    text, _ = serialize_fds(box_model)
    solver, effective = solver_gates(text, AuditConfig())
    assert solver.status == "INCONCLUSIVE"
    assert effective.status == "INCONCLUSIVE"


@pytest.mark.solver
def test_pinned_fds_initialization(box_model):
    executable = os.environ.get("IFCFDS_SOLVER") or shutil.which("fds")
    if not executable:
        pytest.fail("Solver suite requires FDS 6.11.1; it must not silently skip")
    text, _ = serialize_fds(box_model)
    solver, effective = solver_gates(text, AuditConfig(solver_executable=executable))
    output = Path("scripts/out/solver-evidence")
    output.mkdir(parents=True, exist_ok=True)
    (output / "input.fds").write_text(text, encoding="utf-8")
    (output / "initialization.json").write_text(
        solver.model_dump_json(indent=2), encoding="utf-8"
    )
    (output / "effective_geometry.json").write_text(
        effective.model_dump_json(indent=2), encoding="utf-8"
    )
    assert solver.status == "PASS", solver.reason
    # This fixture uses the supported single-mesh OBST subset.
    assert effective.status == "PASS", effective.reason
