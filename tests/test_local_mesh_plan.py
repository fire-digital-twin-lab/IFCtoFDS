"""P4b regression tests for scenario-owned non-overlapping Local MeshPlan."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.fire.mesh_plan import (
    LocalMeshPlanRequest,
    apply_local_mesh_plan,
    local_mesh_evidence,
    resolve_local_mesh_plan,
)
from ifc_to_fds.fire.scenario_emitter import EVSelection
from ifc_to_fds.fire.vehicle_geometry_models import VehicleGeometry
from ifc_to_fds.validation.parser import parse_fds


def _domain() -> BoundingBox:
    return BoundingBox(xmin=0.0, xmax=10.0, ymin=0.0, ymax=10.0, zmin=0.0, zmax=4.0)


def _base_text() -> str:
    return (
        "&HEAD CHID='p4b' /\n"
        "&TIME T_END=0.0 /\n"
        "&MESH ID='BASE', IJK=10,10,4, XB=0,10,0,10,0,4 /\n"
        "&TAIL /\n"
    )


def _bundle() -> SimpleNamespace:
    body = BoundingBox(
        xmin=4.0, xmax=6.0, ymin=4.0, ymax=6.0, zmin=1.0, zmax=2.0
    )
    battery = BoundingBox(
        xmin=4.2, xmax=5.8, ymin=4.2, ymax=5.8, zmin=1.1, zmax=1.3
    )
    geometry = VehicleGeometry(
        mode="PARAMETRIC",
        body_bounds=body,
        floor_z_m=0.5,
        ground_clearance_m=0.5,
        battery_bounds=battery,
        body_from_verified_base=False,
        orientation_status="PARAMETRIC_WORLD_ALIGNED",
        yaw_degrees=0.0,
    )
    selection = EVSelection(
        preset_id="auto-nmc",
        position=(5.0, 5.0, 1.5),
        dimensions=(2.0, 2.0, 1.0),
        geometry_mode="PARAMETRIC",
        floor_z_m=0.5,
        ground_clearance_m=0.5,
    )
    return SimpleNamespace(
        vehicle_geometries=[geometry],
        ev_selections=[selection],
    )


def _request(**updates) -> LocalMeshPlanRequest:
    values = {
        "source_vehicle_index": 0,
        "local_region": BoundingBox(
            xmin=3.0, xmax=7.0, ymin=3.0, ymax=7.0, zmin=0.0, zmax=3.0
        ),
        "refinement_ratio": 2,
    }
    values.update(updates)
    return LocalMeshPlanRequest(**values)


def _interior_overlap(left: BoundingBox, right: BoundingBox) -> bool:
    return (
        min(left.xmax, right.xmax) > max(left.xmin, right.xmin) + 1e-9
        and min(left.ymax, right.ymax) > max(left.ymin, right.ymin) + 1e-9
        and min(left.zmax, right.zmax) > max(left.zmin, right.zmin) + 1e-9
    )


def test_local_mesh_plan_covers_domain_without_overlap_and_resolves_local_dx():
    plan = resolve_local_mesh_plan(
        _base_text(),
        _bundle(),
        _domain(),
        1.0,
        _request(),
    )

    assert plan.local_mesh_id == "P4B_LOCAL_V0"
    assert plan.local_cell_size_xyz_m == pytest.approx((0.5, 0.5, 0.5))
    assert plan.local_mesh().ijk == (8, 8, 6)
    assert plan.local_mesh().total_cells == 384
    assert plan.total_cells > plan.local_mesh().total_cells
    assert len(plan.meshes) == 7

    for index, mesh in enumerate(plan.meshes):
        for other in plan.meshes[index + 1 :]:
            assert not _interior_overlap(mesh.bounds, other.bounds)

    volume = sum(mesh.bounds.dx * mesh.bounds.dy * mesh.bounds.dz for mesh in plan.meshes)
    assert volume == pytest.approx(_domain().dx * _domain().dy * _domain().dz)


def test_local_mesh_plan_rejects_non_lattice_boundary():
    request = _request(
        local_region=BoundingBox(
            xmin=3.1, xmax=7.0, ymin=3.0, ymax=7.0, zmin=0.0, zmax=3.0
        )
    )
    with pytest.raises(ValueError, match="coarse-grid lattice"):
        resolve_local_mesh_plan(_base_text(), _bundle(), _domain(), 1.0, request)


def test_local_mesh_plan_requires_strict_vehicle_containment():
    request = _request(
        local_region=BoundingBox(
            xmin=4.0, xmax=7.0, ymin=3.0, ymax=7.0, zmin=0.0, zmax=3.0
        )
    )
    with pytest.raises(ValueError, match="strictly contain"):
        resolve_local_mesh_plan(_base_text(), _bundle(), _domain(), 1.0, request)


def test_local_mesh_plan_rejects_legacy_vehicle_geometry():
    bundle = _bundle()
    bundle.vehicle_geometries[0] = bundle.vehicle_geometries[0].model_copy(
        update={
            "mode": "LEGACY",
            "orientation_status": "UNVERIFIED",
            "yaw_degrees": None,
        }
    )
    with pytest.raises(ValueError, match="scientific vehicle geometry"):
        resolve_local_mesh_plan(_base_text(), bundle, _domain(), 1.0, _request())


def test_apply_local_mesh_plan_replaces_base_mesh_by_source_spans():
    plan = resolve_local_mesh_plan(
        _base_text(),
        _bundle(),
        _domain(),
        1.0,
        _request(),
    )
    result = apply_local_mesh_plan(_base_text(), plan)
    parsed = parse_fds(result)

    assert not parsed.errors
    assert not parsed.unsupported
    meshes = [record for record in parsed.records if record.kind == "MESH"]
    assert len(meshes) == len(plan.meshes)
    assert "ID='BASE'" not in result
    assert [record.id for record in meshes] == [mesh.id for mesh in plan.meshes]
    assert result.count("&HEAD") == 1
    assert result.count("&TAIL") == 1


def test_local_mesh_evidence_reports_source_local_metrics_without_pass():
    bundle = _bundle()
    plan = resolve_local_mesh_plan(
        _base_text(),
        bundle,
        _domain(),
        1.0,
        _request(),
    )
    evidence = local_mesh_evidence(bundle, plan)

    assert evidence["status"] == "INCONCLUSIVE"
    assert evidence["local_source_mesh_resolved"] is True
    assert evidence["grid_sensitivity_required"] is True
    assert evidence["dx_local_m"] == pytest.approx(0.5)
    assert evidence["ground_clearance_over_dz_local"] == pytest.approx(1.0)
    assert evidence["battery_thickness_over_dz_local"] == pytest.approx(0.4)
    assert evidence["d_star_over_dx_local"] > 0.0
    assert evidence["peak_hrr_basis"] == "PRESET_RANGE_MIDPOINT_ASSUMPTION"


@pytest.mark.solver
def test_p4b_adjacent_coarse_fine_mesh_layout_is_accepted_by_pinned_fds(tmp_path):
    from ifc_to_fds.validation.solver_discovery import resolve_solver_executable

    executable = resolve_solver_executable()
    plan = resolve_local_mesh_plan(
        _base_text(),
        _bundle(),
        _domain(),
        1.0,
        _request(),
    )
    text = apply_local_mesh_plan(_base_text(), plan)
    case_dir = tmp_path / "p4b-local-mesh"
    case_dir.mkdir()
    input_path = case_dir / "input.fds"
    input_path.write_text(text, encoding="utf-8")

    run = subprocess.run(
        [str(executable), "input.fds"],
        cwd=case_dir,
        capture_output=True,
        text=True,
        timeout=45,
        env={
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "PATH": str(executable.parent / "mpi")
            + os.pathsep
            + os.environ.get("PATH", ""),
        },
    )
    log = run.stdout + run.stderr

    evidence_dir = Path("scripts/out/solver-evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": "1.0",
        "claim_id": "MESH-LOCAL-P4B1-001",
        "solver_target": "FDS 6.11.1",
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "stdout_sha256": hashlib.sha256(run.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(run.stderr.encode("utf-8")).hexdigest(),
        "returncode": run.returncode,
        "completed_successfully": "completed successfully" in log.lower(),
        "fatal_error_present": "ERROR:" in log,
        "mesh_count": len(plan.meshes),
        "local_mesh_id": plan.local_mesh_id,
        "refinement_ratio": plan.refinement_ratio,
        "verdict": "PASS" if run.returncode == 0 and "ERROR:" not in log else "FAIL",
        "limitation": (
            "Solver acceptance of one adjacent coarse/fine layout only; "
            "grid sensitivity and solution verification remain pending."
        ),
    }
    (evidence_dir / "p4b-local-mesh-plan.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    assert run.returncode == 0, log
    assert "completed successfully" in log.lower(), log
    assert "ERROR:" not in log, log
