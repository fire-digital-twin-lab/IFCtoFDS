"""Execute P4c2 grid studies with pinned FDS and ingest explicit DEVC outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ifc_to_fds.domain.validation import AuditConfig, GateStatus
from ifc_to_fds.validation.solver import solver_gates

from .grid_sensitivity_analysis import analyze_grid_sensitivity
from .grid_sensitivity_execution_models import (
    ExecutedGridSensitivityStudyEvidence,
    GridSensitivityCaseExecutionEvidence,
    GridSensitivityObservableRequest,
)
from .grid_sensitivity_models import GridSensitivityCaseResult, ResolvedGridSensitivityPlan
from .grid_sensitivity_observables import (
    observations_from_solver_output,
    scenario_observable_metadata,
)
from .grid_sensitivity_outputs import sha256_file
from .grid_sensitivity_plan import render_grid_sensitivity_cases


def _sha256_model(model: Any) -> str:
    payload = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _case_file_hashes(directory: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


def _validated_pass_directory(
    gate_evidence: dict[str, Any],
    *,
    expected_fds_sha256: str,
    expected_solver_version: str,
) -> Path:
    if gate_evidence.get("fds_sha256") != expected_fds_sha256:
        raise ValueError("Pinned solver evidence FDS hash differs from rendered case")
    if expected_solver_version not in gate_evidence.get("reported_versions", []):
        raise ValueError("Pinned solver evidence does not confirm the required version")
    for field in ("sha256", "configuration_sha256"):
        digest = gate_evidence.get(field)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ValueError(f"Pinned solver evidence has invalid {field}")
    directory = gate_evidence.get("directory")
    if not isinstance(directory, str):
        raise ValueError("Pinned solver PASS omitted its evidence directory")
    path = Path(directory)
    if not path.is_dir():
        raise ValueError("Pinned solver evidence directory does not exist")
    return path


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

    chid, metadata = scenario_observable_metadata(scenario_fds, observables)
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
                run_directory = _validated_pass_directory(
                    gate_evidence,
                    expected_fds_sha256=rendered_case["fds_sha256"],
                    expected_solver_version=config.solver_version,
                )
                file_hashes = _case_file_hashes(run_directory)
                observations = observations_from_solver_output(
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
                output_evidence_status = "PASS"
                reason = "Pinned FDS completed and requested DEVC evidence was ingested"
            except ValueError as exc:
                output_evidence_status = "FAIL"
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
                output_evidence_status=output_evidence_status,
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
        case.solver_status == "PASS"
        and case.output_evidence_status == "PASS"
        and case.result is not None
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
