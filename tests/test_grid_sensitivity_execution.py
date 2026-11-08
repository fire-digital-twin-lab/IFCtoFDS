"""P4c2 tests for pinned-FDS execution and strict DEVC output evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.domain.validation import AuditConfig, GateResult, GateStatus
from ifc_to_fds.fire.grid_sensitivity import (
    GridSensitivityObservableRequest,
    GridSensitivityPlanRequest,
    execute_grid_sensitivity_study,
    resolve_grid_sensitivity_plan,
)
from ifc_to_fds.fire.grid_sensitivity_outputs import load_fds_device_series
from ifc_to_fds.fire.scenario_emitter import EVSelection
from ifc_to_fds.fire.vehicle_geometry_models import VehicleGeometry


def _domain() -> BoundingBox:
    return BoundingBox(
        xmin=0.0,
        xmax=10.0,
        ymin=0.0,
        ymax=10.0,
        zmin=0.0,
        zmax=4.0,
    )


def _bundle() -> SimpleNamespace:
    geometry = VehicleGeometry(
        mode="PARAMETRIC",
        body_bounds=BoundingBox(
            xmin=4.0,
            xmax=6.0,
            ymin=4.0,
            ymax=6.0,
            zmin=1.0,
            zmax=2.0,
        ),
        floor_z_m=0.5,
        ground_clearance_m=0.5,
        battery_bounds=BoundingBox(
            xmin=4.2,
            xmax=5.8,
            ymin=4.2,
            ymax=5.8,
            zmin=1.1,
            zmax=1.3,
        ),
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


def _scenario() -> str:
    return (
        "&HEAD CHID='p4c2' /\n"
        "&TIME T_END=0.1 /\n"
        "&MESH ID='BASE', IJK=10,10,4, XB=0,10,0,10,0,4 /\n"
        "&DEVC ID='T_POINT', XYZ=5,5,2.5, QUANTITY='TEMPERATURE' /\n"
        "&TAIL /\n"
    )


def _plan():
    return resolve_grid_sensitivity_plan(
        _scenario(),
        _bundle(),
        _domain(),
        1.0,
        GridSensitivityPlanRequest(
            source_vehicle_index=0,
            local_region=BoundingBox(
                xmin=3.0,
                xmax=7.0,
                ymin=3.0,
                ymax=7.0,
                zmin=0.0,
                zmax=3.0,
            ),
            refinement_ratios=(2, 3, 4),
        ),
    )


def _observable(**updates) -> GridSensitivityObservableRequest:
    payload = {
        "metric_id": "T_POINT_FINAL",
        "device_id": "T_POINT",
        "expected_quantity": "TEMPERATURE",
        "expected_unit": "C",
        "aggregation": "FINAL",
        "time_window_s": (0.0, 0.1),
    }
    payload.update(updates)
    return GridSensitivityObservableRequest(**payload)


def _write_devc(path: Path, device_id: str, unit: str, values: list[float]) -> None:
    path.write_text(
        f'"s","{unit}"\n'
        f'"Time","{device_id}"\n'
        f"0.0,{values[0]}\n"
        f"0.1,{values[1]}\n",
        encoding="utf-8",
    )


def test_devc_parser_reads_split_files_with_units_and_hashes(tmp_path):
    _write_devc(tmp_path / "case_1_devc.csv", "T_POINT", "C", [20.0, 21.0])
    _write_devc(tmp_path / "case_2_devc.csv", "VIS", "m", [10.0, 9.0])

    series = load_fds_device_series(tmp_path, "case")

    assert set(series) == {"T_POINT", "VIS"}
    assert series["T_POINT"].unit == "C"
    assert series["T_POINT"].times_s == pytest.approx((0.0, 0.1))
    assert series["T_POINT"].values == pytest.approx((20.0, 21.0))
    assert series["T_POINT"].source_artifact == "case_1_devc.csv"
    assert len(series["T_POINT"].source_sha256) == 64


def test_devc_parser_rejects_duplicate_device_ids_across_split_files(tmp_path):
    _write_devc(tmp_path / "case_1_devc.csv", "T_POINT", "C", [20.0, 21.0])
    _write_devc(tmp_path / "case_2_devc.csv", "T_POINT", "C", [20.0, 21.0])

    with pytest.raises(ValueError, match="Duplicate FDS DEVC device ID"):
        load_fds_device_series(tmp_path, "case")


def test_devc_parser_rejects_nonmonotonic_time(tmp_path):
    path = tmp_path / "case_devc.csv"
    path.write_text(
        '"s","C"\n'
        '"Time","T_POINT"\n'
        "0.1,20.0\n"
        "0.1,21.0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        load_fds_device_series(tmp_path, "case")


def test_execution_ingests_fake_solver_outputs_and_runs_analysis(tmp_path, monkeypatch):
    counter = 0

    def fake_solver_gates(fds_text, config):
        nonlocal counter
        counter += 1
        case_dir = tmp_path / f"solver-{counter}"
        case_dir.mkdir()
        (case_dir / "run.json").write_text("{}", encoding="utf-8")
        (case_dir / "stdout.log").write_text("completed successfully", encoding="utf-8")
        (case_dir / "stderr.log").write_text("", encoding="utf-8")
        _write_devc(
            case_dir / "p4c2_devc.csv",
            "T_POINT",
            "C",
            [20.0, 100.0 + counter],
        )
        evidence = {
            "directory": str(case_dir),
            "reported_versions": ["6.11.1"],
            "sha256": "a" * 64,
            "configuration_sha256": "b" * 64,
            "fds_sha256": hashlib.sha256(fds_text.encode("utf-8")).hexdigest(),
        }
        return (
            GateResult(
                status=GateStatus.PASS,
                reason="Pinned FDS completed",
                evidence=evidence,
            ),
            GateResult(status=GateStatus.INCONCLUSIVE),
        )

    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_execution.solver_gates",
        fake_solver_gates,
    )
    evidence = execute_grid_sensitivity_study(
        _scenario(),
        _plan(),
        [_observable()],
        AuditConfig(),
        tmp_path / "study",
    )

    assert evidence.execution_status == "COMPLETE"
    assert evidence.status == "INCONCLUSIVE"
    assert evidence.analysis is not None
    assert evidence.analysis.status == "INCONCLUSIVE"
    assert [case.solver_status for case in evidence.cases] == ["PASS", "PASS", "PASS"]
    values = [case.result.observations[0].value for case in evidence.cases if case.result]
    assert values == pytest.approx([101.0, 102.0, 103.0])
    assert evidence.analysis.metrics[0].trend == "MONOTONIC"
    assert list((tmp_path / "study").glob("p4c2-grid-study-*.json"))


def test_execution_withholds_analysis_when_solver_output_is_missing(tmp_path, monkeypatch):
    counter = 0

    def fake_solver_gates(fds_text, config):
        nonlocal counter
        counter += 1
        case_dir = tmp_path / f"missing-{counter}"
        case_dir.mkdir()
        (case_dir / "run.json").write_text("{}", encoding="utf-8")
        (case_dir / "stdout.log").write_text("completed successfully", encoding="utf-8")
        (case_dir / "stderr.log").write_text("", encoding="utf-8")
        return (
            GateResult(
                status=GateStatus.PASS,
                reason="Pinned FDS completed",
                evidence={
                    "directory": str(case_dir),
                    "reported_versions": ["6.11.1"],
                    "sha256": "a" * 64,
                    "configuration_sha256": "b" * 64,
                    "fds_sha256": hashlib.sha256(fds_text.encode("utf-8")).hexdigest(),
                },
            ),
            GateResult(status=GateStatus.INCONCLUSIVE),
        )

    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_execution.solver_gates",
        fake_solver_gates,
    )
    evidence = execute_grid_sensitivity_study(
        _scenario(),
        _plan(),
        [_observable()],
        AuditConfig(),
        tmp_path / "study",
    )

    assert evidence.execution_status == "INCOMPLETE"
    assert evidence.analysis is None
    assert all(case.solver_status == "PASS" for case in evidence.cases)
    assert all(case.result is None for case in evidence.cases)
    assert all("output evidence was rejected" in case.reason for case in evidence.cases)


def test_execution_rejects_solver_input_hash_mismatch(tmp_path, monkeypatch):
    counter = 0

    def fake_solver_gates(fds_text, config):
        nonlocal counter
        counter += 1
        case_dir = tmp_path / f"hash-mismatch-{counter}"
        case_dir.mkdir()
        (case_dir / "run.json").write_text("{}", encoding="utf-8")
        (case_dir / "stdout.log").write_text("completed successfully", encoding="utf-8")
        (case_dir / "stderr.log").write_text("", encoding="utf-8")
        _write_devc(
            case_dir / "p4c2_devc.csv",
            "T_POINT",
            "C",
            [20.0, 21.0],
        )
        return (
            GateResult(
                status=GateStatus.PASS,
                reason="Pinned FDS completed",
                evidence={
                    "directory": str(case_dir),
                    "reported_versions": ["6.11.1"],
                    "sha256": "a" * 64,
                    "configuration_sha256": "b" * 64,
                    "fds_sha256": "f" * 64,
                },
            ),
            GateResult(status=GateStatus.INCONCLUSIVE),
        )

    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_execution.solver_gates",
        fake_solver_gates,
    )
    evidence = execute_grid_sensitivity_study(
        _scenario(),
        _plan(),
        [_observable()],
        AuditConfig(),
        tmp_path / "study",
    )

    assert evidence.execution_status == "INCOMPLETE"
    assert evidence.analysis is None
    assert all(case.result is None for case in evidence.cases)
    assert all("FDS hash differs" in case.reason for case in evidence.cases)


def test_execution_rejects_observable_quantity_drift_before_solver(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Solver must not run when observable metadata is inconsistent")

    monkeypatch.setattr(
        "ifc_to_fds.fire.grid_sensitivity_execution.solver_gates",
        forbidden,
    )
    with pytest.raises(ValueError, match="quantity"):
        execute_grid_sensitivity_study(
            _scenario(),
            _plan(),
            [_observable(expected_quantity="HEAT FLUX")],
            AuditConfig(),
            tmp_path / "study",
        )


@pytest.mark.solver
def test_p4c2_executes_three_pinned_fds_cases_and_ingests_real_devc_output():
    evidence_dir = Path("scripts/out/solver-evidence/p4c2-executed-study")
    evidence = execute_grid_sensitivity_study(
        _scenario(),
        _plan(),
        [_observable()],
        AuditConfig(solver_timeout_s=45.0),
        evidence_dir,
    )

    assert evidence.execution_status == "COMPLETE"
    assert evidence.status == "INCONCLUSIVE"
    assert evidence.analysis is not None
    assert evidence.analysis.acceptance_policy == "NOT_DEFINED"
    assert [case.solver_status for case in evidence.cases] == ["PASS", "PASS", "PASS"]
    for case in evidence.cases:
        assert case.solver_version == "6.11.1"
        assert case.solver_sha256
        assert case.run_json_sha256
        assert case.stdout_sha256
        assert case.stderr_sha256
        assert case.result is not None
        observation = case.result.observations[0]
        assert observation.quantity == "TEMPERATURE"
        assert observation.unit == "C"
        assert observation.source_artifact.endswith("_devc.csv")
        assert len(observation.source_sha256) == 64

    persisted = list(evidence_dir.glob("p4c2-grid-study-*.json"))
    assert persisted
