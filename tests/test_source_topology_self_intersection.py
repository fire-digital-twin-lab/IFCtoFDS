"""Regression for fail-closed source self-intersection topology preflight."""

import pytest
import trimesh

from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.domain.validation import AuditConfig, GateStatus
from ifc_to_fds.geometry.mesh import as_trimesh, valid_solid
from ifc_to_fds.validation import preflight
from ifc_to_fds.validation.checkers.air_path import AirPathTopologyChecker
from ifc_to_fds.validation.checkers.geometry import GeometryChecker
from ifc_to_fds.validation.checkers.openings import OpeningsChecker
from ifc_to_fds.validation.checkers.solver import SolverChecker
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.runner import ValidationRunner


def _overlapping_closed_boxes(box_model):
    first = as_trimesh(box_model.elements[0].mesh)
    second = first.copy()
    second.apply_translation([0.25, 0.25, 0.25])
    combined = trimesh.util.concatenate([first, second])
    mesh = TriangleMesh(
        vertices=combined.vertices.tolist(),
        faces=combined.faces.tolist(),
    )
    assert valid_solid(mesh), "Fixture must pass the historical manifold/volume predicate"
    box_model.elements[0].mesh = mesh
    return box_model


def _minimal_fds():
    return (
        "&HEAD CHID='source_topology' /\n"
        "&TIME T_END=0.0 /\n"
        "&MESH IJK=10,10,10, XB=-2,4,-2,4,-2,5 /\n"
        "&TAIL /\n"
    )


def test_closed_manifold_self_intersection_is_a_preflight_failure_with_witness(box_model):
    model = _overlapping_closed_boxes(box_model)

    evidence = preflight.source_topology_preflight(model)
    issue = evidence[model.elements[0].entity_key]

    assert issue["status"] == "FAIL"
    assert issue["reason"] == "SELF_INTERSECTION"
    assert issue["self_intersection"]["status"] == "CONFIRMED"
    assert issue["self_intersection"]["witness"]["kind"] in {
        "TRIANGLE_CROSSING",
        "COPLANAR_FACE_OVERLAP",
        "COMPONENT_VOLUME_OVERLAP",
    }
    assert preflight.invalid_source_solids(model) == [model.elements[0].entity_key]


def test_validation_runner_blocks_dependent_gates_before_air_path_for_self_intersection(
    box_model, monkeypatch
):
    model = _overlapping_closed_boxes(box_model)

    def forbidden(*args, **kwargs):
        pytest.fail("Dependent gate ran after source self-intersection was confirmed")

    monkeypatch.setattr(AirPathTopologyChecker, "check", forbidden)
    monkeypatch.setattr(OpeningsChecker, "check", forbidden)
    monkeypatch.setattr(SolverChecker, "check", forbidden)

    report = ValidationRunner(
        checkers=[
            GeometryChecker(),
            AirPathTopologyChecker(),
            OpeningsChecker(),
            SolverChecker(),
        ]
    ).validate(
        model,
        _minimal_fds(),
        config=AuditConfig(fail_fast_on_source_errors=True),
    )

    key = model.elements[0].entity_key
    assert report.gates["geometry"].status == GateStatus.FAIL
    assert report.gates["air_path"].status == GateStatus.NOT_RUN
    assert report.gates["openings"].status == GateStatus.NOT_RUN
    assert report.gates["solver"].status == GateStatus.NOT_RUN
    assert report.element_statuses[key] == "UNSUPPORTED"
    issue = report.metrics["source_topology_preflight_evidence"][key]
    assert issue["reason"] == "SELF_INTERSECTION"
    assert issue["self_intersection"]["witness"]


def test_independent_validation_blocks_air_path_and_solver_before_negative_volume_analysis(
    box_model, monkeypatch
):
    model = _overlapping_closed_boxes(box_model)

    def forbidden(*args, **kwargs):
        pytest.fail("Dependent global check ran after topology preflight failure")

    monkeypatch.setattr(
        "ifc_to_fds.validation.checkers.air_path.AirPathTopologyChecker.check",
        forbidden,
    )
    monkeypatch.setattr("ifc_to_fds.validation.engine.solver_gates", forbidden)

    report = run_independent_validation(
        model,
        _minimal_fds(),
        config=AuditConfig(fail_fast_on_source_errors=True),
    )

    key = model.elements[0].entity_key
    assert report.gates["geometry"].status == GateStatus.FAIL
    assert report.gates["air_path"].status == GateStatus.NOT_RUN
    assert report.gates["solver"].status == GateStatus.NOT_RUN
    assert report.element_statuses[key] == "UNSUPPORTED"
    assert report.metrics["source_topology_preflight_evidence"][key]["reason"] == "SELF_INTERSECTION"


def test_uncertain_self_intersection_blocks_dependents_without_becoming_fail(
    box_model, monkeypatch
):
    model = box_model

    monkeypatch.setattr(
        preflight,
        "self_intersection_evidence",
        lambda mesh: {"status": "UNCERTAIN", "reason": "exact predicate backend unavailable"},
    )

    evidence = preflight.source_topology_preflight(model)
    issue = evidence[model.elements[0].entity_key]
    assert issue["status"] == "INCONCLUSIVE"
    assert issue["reason"] == "SELF_INTERSECTION_UNCERTAIN"
    assert preflight.invalid_source_solids(model) == []

    report = ValidationRunner(
        checkers=[
            GeometryChecker(),
            AirPathTopologyChecker(),
            OpeningsChecker(),
            SolverChecker(),
        ]
    ).validate(
        model,
        _minimal_fds(),
        config=AuditConfig(fail_fast_on_source_errors=True),
    )

    assert report.gates["geometry"].status == GateStatus.INCONCLUSIVE
    assert report.gates["air_path"].status == GateStatus.NOT_RUN
    assert report.gates["openings"].status == GateStatus.NOT_RUN
    assert report.gates["solver"].status == GateStatus.NOT_RUN
