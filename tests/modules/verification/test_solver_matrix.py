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


@pytest.mark.solver
@pytest.mark.parametrize("axis,side", [(a, s) for a in range(3) for s in (0, 1)])
def test_real_solver_closing_a_subcell_boundary_gap_is_rejected(axis, side, tmp_path):
    from tests.modules.verification.test_effective_topology import case

    executable = os.environ.get("IFCFDS_SOLVER") or shutil.which("fds")
    assert executable, "Pinned solver required"
    source = [0.4, 0.6, 0.4, 0.6, 0.4, 0.6]
    source[2 * axis:2 * axis + 2] = [0.04, 0.6] if side == 0 else [0.4, 0.96]
    text, _ = case({"wall": source}, {"wall": source})
    solver, effective = solver_gates(text, AuditConfig(solver_executable=executable, solver_evidence_directory=str(tmp_path)))
    assert solver.status == "PASS", solver.reason
    assert effective.status == "FAIL", effective.model_dump_json()
    assert "boundary" in effective.reason.lower()


@pytest.mark.solver
def test_real_solver_multi_surface_geom_proves_triangle_assignments(tmp_path):
    text = solver_cases()["geom"].replace("&GEOM", "&SURF ID='other' /\n&GEOM")
    text = text.replace("SURF_ID='solid'", "SURF_ID='solid','other'").replace("1,4,3,1", "1,4,3,2")
    executable = os.environ.get("IFCFDS_SOLVER") or shutil.which("fds")
    assert executable, "Pinned solver required"
    solver, effective = solver_gates(text, AuditConfig(solver_executable=executable, solver_evidence_directory=str(tmp_path)))
    assert solver.status == "PASS", solver.reason
    assert solver.evidence["solver_surface_geometry"]["status"] == "PASS"
    assert effective.status == "INCONCLUSIVE"


@pytest.mark.solver
@pytest.mark.parametrize("scenario", ["covered_face", "boundary_low", "boundary_high", "gap_low", "gap_high"])
def test_real_solver_boundary_union_and_print_precision(scenario, tmp_path):
    from tests.modules.verification.test_effective_topology import case

    executable = os.environ.get("IFCFDS_SOLVER") or shutil.which("fds")
    assert executable, "Pinned solver required"
    if scenario == "covered_face":
        # The boundary corridor is already solid, while the protruding part
        # keeps both source identities observable in native SMV evidence.
        boxes = {"outer": [0, 0.2, 0, 1, 0, 1], "protruding": [0.04, 0.5, 0.4, 0.6, 0.4, 0.6]}
        text, _ = case(boxes, boxes)
    else:
        side = int(scenario.endswith("high"))
        offset = 0.12345002 if side == 0 else 0.12344998
        domain = [offset, offset + 1] * 3
        box = [offset + 0.4, offset + 0.6] * 3
        box[side] = offset + ((0.96 if side else 0.04) if scenario.startswith("gap") else side)
        text, _ = case({"wall": box}, {"wall": box}, domain)
    solver, effective = solver_gates(
        text, AuditConfig(solver_executable=executable, solver_evidence_directory=str(tmp_path))
    )
    assert solver.status == "PASS", solver.reason
    assert effective.status == ("FAIL" if scenario.startswith("gap") else "PASS"), effective.reason
    if scenario.startswith("gap"):
        assert "boundary" in effective.reason.lower()
