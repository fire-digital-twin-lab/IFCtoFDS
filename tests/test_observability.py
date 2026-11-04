"""Regression checks for canonical bilingual diagnostic events."""

import json

import pytest

from ifc_to_fds.diagnostics import execution_scope, operation, progress
from ifc_to_fds.observability import (
    DiagnosticEvent, append_event, catalog, rebuild_localized_logs,
    render_event, validate_catalogs,
)


def test_catalog_consistency():
    validate_catalogs()
    assert set(catalog("en")) == set(catalog("vi"))
    with pytest.raises(ValueError):
        catalog("fr")


def test_language_independent_event_contract():
    event = DiagnosticEvent(
        code="IFCFDS.STAGE.RUNNING", level="INFO", stage="GEOMETRY",
        job_id="job-001", entity_key="source:9923",
        params={"stage": "GEOMETRY", "state": "RUNNING", "elapsed_s": 0},
        timestamp="2026-11-04T08:30:00Z",
    )
    record = event.to_record()
    assert record["entity_key"] == "source:9923"
    assert "GEOMETRY" in render_event(record, "en")
    assert "đang thực hiện" in render_event(record, "vi")
    assert record["level"] == "INFO"


def test_roundtrip_and_rebuild_from_canonical_jsonl(tmp_path):
    event = DiagnosticEvent(
        code="IFCFDS.STAGE.COMPLETED", level="INFO", stage="MAPPING",
        job_id="job-001", timestamp="2026-11-04T08:30:00Z",
        params={"stage": "MAPPING", "elapsed_s": 2.5, "state": "COMPLETED"},
    )
    append_event(tmp_path, event)
    canonical = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    english = (tmp_path / "events.en.log").read_text(encoding="utf-8")
    vietnamese = (tmp_path / "events.vi.log").read_text(encoding="utf-8")
    assert json.loads(canonical)["params"]["elapsed_s"] == 2.5
    assert "completed" in english
    assert "hoàn tất" in vietnamese
    (tmp_path / "events.vi.log").write_text("bad translation", encoding="utf-8")
    rebuild_localized_logs(tmp_path)
    assert (tmp_path / "events.en.log").read_text(encoding="utf-8") == english
    assert (tmp_path / "events.vi.log").read_text(encoding="utf-8") == vietnamese
    assert (tmp_path / "events.jsonl").read_text(encoding="utf-8") == canonical


def test_validation_and_no_unregistered_event_writes(tmp_path):
    with pytest.raises(ValueError):
        DiagnosticEvent(code="UNKNOWN", level="INFO", stage="MAPPING")
    with pytest.raises(ValueError):
        DiagnosticEvent(code="IFCFDS.STAGE.RUNNING", level="SUCCESS", stage="MAPPING")
    with pytest.raises(ValueError):
        append_event(
            tmp_path, DiagnosticEvent(code="IFCFDS.UNKNOWN", level="INFO", stage="TEST")
        )
    assert not (tmp_path / "events.jsonl").exists()


def test_rendering_escapes_embedded_newlines():
    rendered = render_event({
        "timestamp": "2026-11-04T08:30:00Z", "level": "ERROR",
        "code": "IFCFDS.JOB.FAILED",
        "params": {"stage": "VALIDATION\nFORGED", "error_type": "ValueError"},
    }, "en")
    assert "\n" not in rendered
    assert r"\nFORGED" in rendered


def test_legacy_progress_unmodified(tmp_path):
    with execution_scope(tmp_path):
        progress("GEOMETRY", "RUNNING", 0)
        progress("GEOMETRY", "COMPLETED", 1.25, count=2)
    original = json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))
    assert original == {
        "stage": "GEOMETRY", "state": "COMPLETED",
        "elapsed_s": 1.25, "count": 2,
    }
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["code"] for item in events] == [
        "IFCFDS.STAGE.RUNNING", "IFCFDS.STAGE.COMPLETED",
    ]
    assert len((tmp_path / "events.en.log").read_text(encoding="utf-8").splitlines()) == 2
    assert len((tmp_path / "events.vi.log").read_text(encoding="utf-8").splitlines()) == 2


def test_operation_failure_remains_failure(tmp_path):
    @operation("SOURCE")
    def broken():
        raise RuntimeError("example")
    with execution_scope(tmp_path):
        with pytest.raises(RuntimeError, match="example"):
            broken()
    assert json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))["state"] == "FAILED"
    assert "IFCFDS.STAGE.FAILED" in (tmp_path / "events.jsonl").read_text(encoding="utf-8")
