"""Execute P4c2 grid studies with pinned FDS and ingest explicit DEVC outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ifc_to_fds.domain.validation import AuditConfig, GateStatus
from ifc_to_fds.validation.parser import FDSRecord, parse_fds
from ifc_to_fds.validation.solver import solver_gates

from .grid_sensitivity_analysis import analyze_grid_sensitivity
from .grid_sensitivity_execution_models import (
    ExecutedGridSensitivityStudyEvidence,
    GridSensitivityCaseExecutionEvidence,
    GridSensitivityObservableRequest,
)
from .grid_sensitivity_models import (
    GridSensitivityCaseResult,
    GridSensitivityObservation,
    ResolvedGridSensitivityPlan,
)
from .grid_sensitivity_outputs import DeviceTimeSeries, load_fds_device_series, sha256_file
from .grid_sensitivity_plan import render_grid_sensitivity_cases


def _sha256_model(model: Any) -> str:
    payload = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _single_value(record: FDSRecord, field: str) -> Any | None:
    values = record.values.get(field, [])
    if not values:
        return None
    if len(values) != 1:
        raise ValueError(f"{record.kind} {record.id}: {field} must have one value")
    return values[0]


def _scenario_observable_metadata(
    scenario_fds: str,
    requests: list[GridSensitivityObservableRequest],
) -> tuple[str, dict[str, dict[str, Any]]]:
    parsed = parse_fds(scenario_fds)
    if parsed.errors or parsed.unsupported:
        raise ValueError(
            "P4c2 requires parser-clean scientific FDS before solver execution"
        )

    heads = [record for record in parsed.records if record.kind == "HEAD"]
    if len(heads) != 1:
        raise ValueError("P4c2 requires exactly one FDS HEAD record")
    chid = _single_value(heads[0], "CHID")
    if not isinstance(chid, str) or not chid.strip():
        raise ValueError("P4c2 requires a non-empty HEAD.CHID")
    chid = chid.strip()

    metric_ids = [request.metric_id for request in requests]
    device_ids = [request.device_id for request in requests]
    if not requests:
        raise ValueError("P4c2 requires at least one explicit DEVC observable")
    if len(metric_ids) != len(set(metric_ids)):
        raise ValueError("P4c2 observable metric_id values must be unique")
    if len(device_ids) != len(set(device_ids)):
        raise ValueError("P4c2 observable device_id values must be unique")

    metadata: dict[str, dict[str, Any]] = {}
    for request in requests:
        matches = [
            record
            for record in parsed.records
            if record.kind == "DEVC" and record.id == request.device_id
        ]
        if len(matches) != 1:
            raise ValueError(
                f"P4c2 requires exactly one DEVC with ID {request.device_id!r}"
            )
        record = matches[0]
        quantity = _single_value(record, "QUANTITY")
        if not isinstance(quantity, str) or not quantity.strip():
            raise ValueError(
                f"P4c2 supports only DEVC records with explicit QUANTITY: "
                f"{request.device_id}"
            )
        if quantity.strip().upper() != request.expected_quantity.strip().upper():
            raise ValueError(
                f"DEVC {request.device_id!r} quantity {quantity!r} differs from "
                f"expected {request.expected_quantity!r}"
            )

        xyz = record.values.get("XYZ", [])
        if len(xyz) != 3:
            raise ValueError(
                f"P4c2 currently supports only point DEVC XYZ observables: "
                f"{request.device_id}"
            )
        location = tuple(float(value) for value in xyz)

        declared_units = _single_value(record, "UNITS")
        if (
            declared_units is not None
            and str(declared_units).strip() != request.expected_unit.strip()
        ):
            raise ValueError(
                f"DEVC {request.device_id!r} declared UNITS {declared_units!r} "
                f"differs from expected {request.expected_unit!r}"
            )

        metadata[request.metric_id] = {
            "device_id": request.device_id,
            "quantity": quantity.strip(),
            "location_m": location,
        }
    return chid, metadata


def _aggregate(
    series: DeviceTimeSeries,
    request: GridSensitivityObservableRequest,
) -> float:
    samples = list(zip(series.times_s, series.values, strict=True))
    if request.time_window_s is not None:
        start, stop = request.time_window_s
        samples = [(time_s, value) for time_s, value in samples if start <= time_s <= stop]
    if not samples:
        raise ValueError(
            f"No FDS DEVC samples remain for metric {request.metric_id!r} "
            "inside the requested time window"
        )

    values = [value for _, value in samples]
    if request.aggregation == "MAX":
        return max(values)
    if request.aggregation == "MIN":
        return min(values)
    if request.aggregation == "FINAL":
        return samples[-1][1]
    raise ValueError(f"Unsupported P4c2 aggregation: {request.aggregation}")


def _observations_from_solver_output(
    directory: Path,
    chid: str,
    requests: list[GridSensitivityObservableRequest],
    metadata: dict[str, dict[str, Any]],
) -> list[GridSensitivityObservation]:
    series_by_id = load_fds_device_series(directory, chid)
    observations: list[GridSensitivityObservation] = []
    for request in requests:
        series = series_by_id.get(request.device_id)
        if series is None:
            raise ValueError(
                f"FDS DEVC output does not contain requested device {request.device_id!r}"
            )
        if series.unit != request.expected_unit.strip():
            raise ValueError(
                f"FDS DEVC unit {series.unit!r} for {request.device_id!r} "
                f"differs from expected {request.expected_unit!r}"
            )
        descriptor = metadata[request.metric_id]
        observations.append(
            GridSensitivityObservation(
                metric_id=request.metric_id,
                quantity=descriptor["quantity"],
                unit=series.unit,
                value=_aggregate(series, request),
                aggregation=request.aggregation,
                location_m=descriptor["location_m"],
                time_window_s=request.time_window_s,
                source_artifact=series.source_artifact,
                source_sha256=series.source_sha256,
            )
        )
    return observations


def _case_file_hashes(directory: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


def execute_grid_sensitivity_study(
    scenario_fds: str,
    plan: ResolvedGridSensitivityPlan,
    observables: list[GridSensitivityObservableRequest],
    config: AuditConfig,
    evidence_directory: Path,
) -> ExecutedGridSensitivityStudyEvidence:
    """Run three pinned-FDS cases and ingest explicit device outputs fail-closed."""

    if hashlib.sha256(scenario_fds.encode("utf-8")).hexdigest() != plan.scenario_invariant_sha256:
        raise ValueError("Scenario differs from the resolved grid-sensitivity plan")

    chid, metadata = _scenario_observable_metadata(scenario_fds, observables)
    rendered = render_grid_sensitivity_cases(scenario_fds, plan)
    evidence_directory = Path(evidence_directory).resolve()
    evidence_directory.mkdir(parents=True, exist_ok=True)
    solver_directory = evidence_directory / "solver-runs"
    solver_directory.mkdir(parents=True, exist_ok=True)
    solver_config = config.model_copy(
        update={"solver_evidence_directory": str(solver_directory)}
    )

    case_evidence: list[GridSensitivityCaseExecutionEvidence] = []
    results: list[GridSensitivityCaseResult] = []
    for case in plan.cases:
        rendered_case = rendered[case.level]
        solver_gate, _ = solver_gates(rendered_case["fds_text"], solver_config)
        gate_evidence = solver_gate.evidence
        run_directory_value = gate_evidence.get("directory")
        run_directory = (
            Path(run_directory_value) if isinstance(run_directory_value, str) else None
        )
        file_hashes = (
            _case_file_hashes(run_directory)
            if run_directory is not None and run_directory.is_dir()
            else {}
        )

        result = None
        reason = solver_gate.reason or "Pinned FDS produced no execution reason"
        if solver_gate.status == GateStatus.PASS:
            try:
                if run_directory is None:
                    raise ValueError("Pinned solver PASS omitted its evidence directory")
                observations = _observations_from_solver_output(
                    run_directory,
                    chid,
                    observables,
                    metadata,
                )
                result = GridSensitivityCaseResult(
                    level=case.level,
                    refinement_ratio=case.refinement_ratio,
                    local_dx_m=case.local_dx_m,
                    scenario_invariant_sha256=plan.scenario_invariant_sha256,
                    fds_sha256=rendered_case["fds_sha256"],
                    observations=observations,
                )
                results.append(result)
                reason = "Pinned FDS completed and requested DEVC evidence was ingested"
            except ValueError as exc:
                reason = f"Pinned FDS completed but output evidence was rejected: {exc}"

        reported_versions = gate_evidence.get("reported_versions", [])
        solver_version = (
            config.solver_version
            if config.solver_version in reported_versions
            else None
        )
        case_evidence.append(
            GridSensitivityCaseExecutionEvidence(
                level=case.level,
                refinement_ratio=case.refinement_ratio,
                local_dx_m=case.local_dx_m,
                fds_sha256=rendered_case["fds_sha256"],
                solver_status=solver_gate.status.value,
                reason=reason,
                solver_version=solver_version,
                solver_sha256=gate_evidence.get("sha256"),
                configuration_sha256=gate_evidence.get("configuration_sha256"),
                run_json_sha256=file_hashes.get("run.json"),
                stdout_sha256=file_hashes.get("stdout.log"),
                stderr_sha256=file_hashes.get("stderr.log"),
                output_files_sha256=file_hashes,
                result=result,
            )
        )

    complete = len(results) == 3 and all(
        case.solver_status == "PASS" and case.result is not None
        for case in case_evidence
    )
    analysis = analyze_grid_sensitivity(results) if complete else None
    study = ExecutedGridSensitivityStudyEvidence(
        execution_status="COMPLETE" if complete else "INCOMPLETE",
        reason=(
            "Three pinned FDS cases completed and comparable DEVC observables were "
            "ingested; no reviewed convergence acceptance or numerical-uncertainty "
            "model is defined."
            if complete
            else "At least one pinned FDS case or requested output artifact was not "
            "accepted; comparative grid analysis was withheld."
        ),
        plan_sha256=_sha256_model(plan),
        scenario_invariant_sha256=plan.scenario_invariant_sha256,
        cases=case_evidence,
        analysis=analysis,
    )
    output_path = evidence_directory / (
        f"p4c2-grid-study-{study.plan_sha256[:12]}.json"
    )
    output_path.write_text(
        study.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return study
