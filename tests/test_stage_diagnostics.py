import json
from pathlib import Path
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
    assert "FileNotFoundError" in diagnostic["name"]
    assert "vertices" not in diagnostic and "fds_text" not in diagnostic


def test_nested_operations_restore_enclosing_stage(tmp_path):
    checkpoint = {}

    @operation("INNER_STAGE")
    def inner():
        return 42

    @operation("OUTER_STAGE")
    def outer():
        inner()
        # After inner completes, progress.json should reflect outer still running
        progress_data = json.loads((tmp_path / "progress.json").read_text())
        checkpoint["stage"] = progress_data["stage"]
        checkpoint["state"] = progress_data["state"]

    with execution_scope(tmp_path):
        outer()
        final_data = json.loads((tmp_path / "progress.json").read_text())

    assert checkpoint["stage"] == "OUTER_STAGE"
    assert checkpoint["state"] == "RUNNING"
    assert final_data["stage"] == "OUTER_STAGE"
    assert final_data["state"] == "COMPLETED"


def test_safe_replace_retries_and_handles_locked_file(tmp_path, monkeypatch):
    from ifc_to_fds.diagnostics import _safe_replace

    src = tmp_path / "test.tmp"
    dst = tmp_path / "test.json"
    src.write_text("hello", encoding="utf-8")

    attempts = 0

    def fail_replace(self, target):
        nonlocal attempts
        attempts += 1
        raise PermissionError("Locked on Windows")

    monkeypatch.setattr(Path, "replace", fail_replace)
    # _safe_replace should not raise PermissionError even when locked
    _safe_replace(src, dst, max_attempts=3)
    assert attempts == 3

