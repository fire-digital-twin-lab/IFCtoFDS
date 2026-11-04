"""R10-04: post-engine independent audit and MEP regression boundaries."""

import ast
from pathlib import Path

from ifc_to_fds.domain.validation.model import AcceptanceReport, GateResult, GateStatus
from ifc_to_fds.application.services.audit_integrity import (
    apply_independent_source_integrity,
)
from ifc_to_fds.application.services.audit_mep_coverage import (
    apply_mep_and_coverage,
)


def test_audit_use_case_orchestrates_existing_engine_before_post_checks():
    from ifc_to_fds.application.use_cases import audit_conversion

    tree = ast.parse(Path(audit_conversion.__file__).read_text(encoding="utf-8"))
    execute = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "execute"
    )
    # AST traversal is breadth-first, not source order: compare line numbers.
    calls = {
        node.func.id: node.lineno
        for node in ast.walk(execute)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    for required in (
        "run_independent_validation", "apply_independent_source_integrity",
        "apply_mep_and_coverage", "golden_gate",
    ):
        assert required in calls
    assert (
        calls["run_independent_validation"]
        < calls["apply_independent_source_integrity"]
        < calls["apply_mep_and_coverage"]
        < calls["golden_gate"]
    )


def test_topology_preflight_must_not_claim_geometry_package_verified(box_model, monkeypatch):
    from ifc_to_fds.application.services import audit_integrity

    def unexpected_package_audit(*args):
        raise AssertionError("Package audit must not run during preflight rejection")

    monkeypatch.setattr(audit_integrity, "audit_package", unexpected_package_audit)
    from ifc_to_fds.mapping import boundary

    monkeypatch.setattr(boundary, "finalize_boundary", lambda *args: None)
    manifest = type("Manifest", (), {
        "records": [], "schema_version": "0.5.0",
        "geometry_package_sha256": None,
        "simulation_domain": (
            box_model.simulation_domain.model_dump() if box_model.simulation_domain else None
        ),
        "sources": [source.model_dump(mode="json") for source in box_model.sources],
    })()
    report = AcceptanceReport(
        gates={
            "geometry_preservation": GateResult(status=GateStatus.NOT_RUN),
            "source_inventory": GateResult(status=GateStatus.NOT_RUN),
        },
        metrics={"source_topology_preflight_rejected": ["fixture:1"]},
    )
    apply_independent_source_integrity(
        box_model, "", manifest, None, report, object()
    )
    assert report.gates["geometry_preservation"].status == GateStatus.NOT_RUN


def test_saved_mep_graph_absent_cannot_become_pass(box_model):
    report = AcceptanceReport(
        gates={"mep": GateResult(status=GateStatus.PASS),
               "hvac": GateResult(status=GateStatus.NOT_APPLICABLE)}
    )
    apply_mep_and_coverage(box_model, report, {})
    assert report.gates["mep"].status == GateStatus.INCONCLUSIVE
    assert report.coverage["mep_systems"]["VENTILATION"]["source_count"] >= 0


def test_saved_mep_graph_mismatch_forces_fail(box_model):
    report = AcceptanceReport(
        gates={"mep": GateResult(status=GateStatus.PASS),
               "hvac": GateResult(status=GateStatus.NOT_APPLICABLE)}
    )
    apply_mep_and_coverage(box_model, report, {"mep_graph": {"tampered": True}})
    assert report.gates["mep"].status == GateStatus.FAIL
