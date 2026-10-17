import json
import pytest
from ifc_to_fds.diagnostics import execution_scope, operation, failure_diagnostic


def test_innermost_error_stage_and_job_are_preserved(tmp_path):
    @operation("IFC_GEOMETRY")
    def geometry():
        raise RuntimeError("Kernel unavailable")

    @operation("VALIDATION")
    def validation():
        geometry()

    with execution_scope(tmp_path):
        with pytest.raises(RuntimeError) as caught:
            validation()
        diagnostic = failure_diagnostic(caught.value, "job-fixture")
    assert diagnostic["stage"] == "IFC_GEOMETRY"
    assert diagnostic["jobId"] == "job-fixture"
    assert "geometry" in diagnostic["stack"]
    assert json.loads((tmp_path / "progress.json").read_text())["state"] == "FAILED"
    assert not (tmp_path / "progress.tmp").exists()


def test_worker_failure_keeps_downloadable_diagnostic(tmp_path):
    from ifc_to_fds.adapters.jobs import WorkerRunner

    (tmp_path / "request.json").write_text(
        json.dumps(
            {
                "job_id": "actual-job-id",
                "paths": [str(tmp_path / "missing.ifc")],
                "configuration": {},
            }
        )
    )
    assert WorkerRunner.run(tmp_path) == 1
    diagnostic = json.loads((tmp_path / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostic["stage"] == "IFC_READ"
    assert diagnostic["jobId"] == "actual-job-id"
    assert diagnostic["name"] == "FileNotFoundError"
    assert "vertices" not in diagnostic and "fds_text" not in diagnostic
