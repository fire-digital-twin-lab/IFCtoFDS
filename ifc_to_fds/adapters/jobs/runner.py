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
            from ifc_to_fds.pipeline import convert, save_artifacts

            request = json.loads(
                (directory / "request.json").read_text(encoding="utf-8")
            )
            job_id = request.get("job_id", job_id)
            if request.get("mode") == "inventory":
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
            else:
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
