import os
from pathlib import Path
import shutil

import pytest

from ifc_to_fds.domain.validation import AuditConfig
from ifc_to_fds.modules.verification.api import solver_gates
from tests.support.solver_cases import solver_cases


@pytest.mark.solver
@pytest.mark.parametrize("name", list(solver_cases()))
def test_real_solver_matrix(name, tmp_path):
    executable = os.environ.get("IFCFDS_SOLVER") or shutil.which("fds")
    assert executable, "Solver tests require the pinned executable; absence is not PASS"
    solver, effective = solver_gates(
        solver_cases()[name],
        AuditConfig(
            solver_executable=executable,
            solver_evidence_directory=str(tmp_path),
        ),
    )
    assert solver.status == (
        "FAIL" if name == "invalid_geom" else "PASS"
    ), solver.reason
    expected = (
        "PASS" if name in ("obst", "hole", "vent", "multi_mesh") else "INCONCLUSIVE"
    )
    assert effective.status == expected, effective.reason
    assert Path(solver.evidence["directory"], "audit.fds").is_file()
    assert solver.evidence["reported_versions"]
    if name == "geom":
        assert solver.evidence["solver_surface_geometry"]["status"] == "PASS"


@pytest.mark.solver
def test_authored_mep_geometry_initializes_in_real_fds(tmp_path):
    from ifc_to_fds.pipeline import convert
    from tests.support.mep_geometry import create_mep_geometry_ifc

    executable = os.environ.get("IFCFDS_SOLVER") or shutil.which("fds")
    assert executable, "Pinned FDS is required"
    source = tmp_path / "mep.ifc"
    create_mep_geometry_ifc(source)
    converted = convert(
        [source],
        {"profile": "geometry-fidelity"},
        output_directory=tmp_path / "conversion",
    )
    assert converted["mapping_status"] == "MAPPING_VERIFIED"
    solver, effective = solver_gates(
        converted["fds_text"],
        AuditConfig(
            solver_executable=executable,
            solver_evidence_directory=str(tmp_path / "solver"),
        ),
    )
    assert solver.status == "PASS", solver.reason
    surfaces = solver.evidence["solver_surface_geometry"]
    assert surfaces["status"] == "PASS"
    assert len(surfaces["evidence"]["files"]) == 8
    assert (
        effective.status == "INCONCLUSIVE"
    ), "GEOM cut-cell fidelity must not be inferred from initialization"


@pytest.mark.solver
@pytest.mark.parametrize("name", ["obst", "geom", "hole", "vent", "multi_mesh"])
def test_real_solver_advances_time_for_geometry_cases(name, tmp_path):
    from ifc_to_fds.modules.verification.api import prepare_geometry_run

    executable = os.environ.get("IFCFDS_SOLVER") or shutil.which("fds")
    assert executable, "A real pinned solver is required"
    text, derivation = prepare_geometry_run(solver_cases()[name], 1.0)
    gate, _ = solver_gates(
        text,
        AuditConfig(
            solver_executable=executable, solver_evidence_directory=str(tmp_path)
        ),
    )
    assert gate.status == "PASS", gate.model_dump_json()
    assert gate.evidence["fds_sha256"] == derivation["derived_sha256"]
    completion = gate.evidence["completion"]
    assert completion["mode"] == "TRANSIENT"
    assert completion["observed_end_s"] >= 1.0
    assert completion["time_steps"] > 0


@pytest.mark.solver
def test_authored_mep_geometry_runs_beyond_setup(tmp_path):
    from ifc_to_fds.pipeline import convert
    from ifc_to_fds.modules.verification.api import prepare_geometry_run
    from tests.support.mep_geometry import create_mep_geometry_ifc

    executable = os.environ.get("IFCFDS_SOLVER") or shutil.which("fds")
    assert executable, "A real pinned solver is required"
    source = tmp_path / "mep.ifc"
    create_mep_geometry_ifc(source)
    result = convert(
        [source],
        {"profile": "geometry-fidelity"},
        output_directory=tmp_path / "conversion",
    )
    assert result["mapping_status"] == "MAPPING_VERIFIED"
    text, derivation = prepare_geometry_run(result["fds_text"], 1.0)
    gate, effective = solver_gates(
        text,
        AuditConfig(
            solver_executable=executable,
            solver_evidence_directory=str(tmp_path / "solver"),
        ),
    )
    assert gate.status == "PASS", gate.model_dump_json()
    assert gate.evidence["completion"]["mode"] == "TRANSIENT"
    assert gate.evidence["completion"]["observed_end_s"] >= 1.0
    assert gate.evidence["completion"]["time_steps"] > 0
    assert gate.evidence["fds_sha256"] == derivation["derived_sha256"]
    assert effective.status == "INCONCLUSIVE"
    assert gate.evidence["solver_surface_geometry"]["status"] == "PASS"
    assert result["report"]["simulation_status"] == "INCONCLUSIVE"
