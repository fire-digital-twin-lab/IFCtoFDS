"""Worker execution runner calling application use cases."""

import json
from pathlib import Path
from typing import Any


class WorkerRunner:
    """Executes background jobs by invoking application use cases."""

    @staticmethod
    def run(directory: str | Path) -> int:
        from ifc_to_fds.diagnostics import execution_scope

        with execution_scope(directory):
            return WorkerRunner.execute(directory)

    @staticmethod
    def execute(directory: str | Path) -> int:
        directory = Path(directory)
        job_id = directory.name
        try:
            request = json.loads(
                (directory / "request.json").read_text(encoding="utf-8")
            )
            job_id = request.get("job_id", job_id)
            if request.get("mode") == "preview":
                from ifc_to_fds.application.use_cases.preview_model import preview_model

                result = preview_model(request["paths"], directory)
            elif request.get("mode") == "inventory":
                from ifc_to_fds.core.inventory import extract_inventory

                models = [extract_inventory(path)[0] for path in request["paths"]]
                result: dict[str, Any] = dict(
                    total_elements=sum(len(m.elements) for m in models),
                    storeys=[s.name for m in models for s in m.storey_references],
                    storey_references=[
                        s.model_dump() for m in models for s in m.storey_references
                    ],
                    sources=[m.source.model_dump() for m in models],
                )
            elif request.get("mode") == "scenario":
                from ifc_to_fds.fire.mesh_gate import check_mesh_resolution

                scenario_payload = request.get("configuration") or {}
                if not scenario_payload and (directory / "scenario.json").is_file():
                    try:
                        scenario_payload = json.loads(
                            (directory / "scenario.json").read_text(encoding="utf-8")
                        )
                    except Exception:
                        scenario_payload = {}
                scenario_input = (
                    scenario_payload.get("scenario_data")
                    if isinstance(scenario_payload, dict) and "scenario_data" in scenario_payload
                    else scenario_payload
                )
                cell_size = (
                    scenario_payload.get("cell_size", 0.2)
                    if isinstance(scenario_payload, dict)
                    else 0.2
                )
                mesh_gate = check_mesh_resolution(scenario_input, cell_size=cell_size)

                peak_hrr_mw = 0.0
                if isinstance(scenario_input, dict):
                    peak_hrr_mw = (
                        scenario_input.get("total_peak_hrr_mw")
                        or scenario_input.get("peak_hrr_mw")
                        or 0.0
                    )
                elif hasattr(scenario_input, "total_peak_hrr_mw"):
                    peak_hrr_mw = scenario_input.total_peak_hrr_mw
                if not peak_hrr_mw and isinstance(scenario_payload, dict):
                    peak_hrr_mw = (
                        scenario_payload.get("total_peak_hrr_mw")
                        or scenario_payload.get("peak_hrr_mw")
                        or 0.0
                    )
                if not peak_hrr_mw and mesh_gate.evidence:
                    peak_hrr_mw = (mesh_gate.evidence.get("peak_hrr_kw") or 0.0) / 1000.0

                result = {
                    "status": "COMPLETED",
                    "verdict": mesh_gate.status.value,
                    "mesh_status": mesh_gate.status.value,
                    "peak_hrr_mw": float(peak_hrr_mw),
                    "evidence": mesh_gate.evidence,
                }
            else:
                from ifc_to_fds.pipeline import convert, save_artifacts

                result = convert(
                    request["paths"], request["configuration"], str(directory)
                )
                save_artifacts(result, directory / "model.fds")
                from ifc_to_fds.results import public_result

                result = public_result(result)
            if request.get("mode") == "inventory":
                from ifc_to_fds.results import research_context

                result["research"] = research_context(result["sources"], {})
            (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")
            return 0
        except Exception as exc:
            from ifc_to_fds.diagnostics import failure_diagnostic

            diagnostic = failure_diagnostic(exc, job_id)
            (directory / "diagnostics.json").write_text(
                json.dumps(diagnostic), encoding="utf-8"
            )
            (directory / "error.txt").write_text(
                f"{type(exc).__name__}: {exc}", encoding="utf-8"
            )
            return 1
