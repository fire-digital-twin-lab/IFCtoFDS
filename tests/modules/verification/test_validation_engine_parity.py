"""Parity tests between monolithic engine.py and modular runner.py.

Verifies that run_independent_validation and ValidationRunner().validate produce
identical verdicts, element statuses, and gate statuses across diverse validation scenarios.
"""

import re
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.runner import ValidationRunner


SHARED_GATES: list[str] = [
    "syntax",
    "domain",
    "traceability",
    "scope",
    "geometry",
    "structural_completeness",
    "air_path",
    "openings",
    "mep",
    "representation",
    "boundary",
]


def assert_validation_parity(rep_engine, rep_runner, require_solver=False):
    """Asserts deep semantic parity between the two validation implementations."""
    # 1. Overall Acceptance Status
    assert rep_engine.status == rep_runner.status, (
        f"Status mismatch: engine={rep_engine.status} vs runner={rep_runner.status}"
    )
    assert rep_engine.mapping_status == rep_runner.mapping_status, (
        f"Mapping status mismatch: engine={rep_engine.mapping_status} vs runner={rep_runner.mapping_status}"
    )

    # 2. Gate-by-Gate Evaluation Status
    gates_to_check: list[str] = list(SHARED_GATES)
    if require_solver:
        gates_to_check.append("solver")

    for gate in gates_to_check:
        st_eng = rep_engine.gates[gate].status
        st_run = rep_runner.gates[gate].status
        assert st_eng == st_run, (
            f"Gate {gate!r} status mismatch: engine={st_eng} vs runner={st_run}"
        )

    # 3. Element-Level Dispositions
    assert rep_engine.element_statuses == rep_runner.element_statuses, (
        f"Element statuses mismatch:\nEngine: {rep_engine.element_statuses}\nRunner: {rep_runner.element_statuses}"
    )

    # 4. Summary Classification Counters
    assert rep_engine.matched_count == rep_runner.matched_count
    assert rep_engine.missing_count == rep_runner.missing_count
    assert rep_engine.deviated_count == rep_runner.deviated_count
    assert rep_engine.excluded_count == rep_runner.excluded_count


def test_parity_clean_box_model(box_model):
    """Case 1: Baseline valid box model and FDS."""
    fds_text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, fds_text)

    rep_eng = run_independent_validation(box_model, fds_text, manifest)
    rep_run = ValidationRunner().validate(box_model, fds_text, manifest)

    assert_validation_parity(rep_eng, rep_run)
    assert rep_eng.gates["geometry"].status == "PASS"
    assert rep_eng.gates["traceability"].status == "PASS"
    assert rep_eng.element_statuses[box_model.elements[0].entity_key] == "MATCHED"


def test_parity_geometry_shifted(box_model):
    """Case 2: Shifted obstacle coordinates must be rejected by both."""
    fds_text, _ = serialize_fds(box_model)
    shifted = fds_text.replace("XB=0,2,0,1,0,3", "XB=2.0000,4.0000,0.0000,1.0000,0.0000,3.0000")
    manifest = build_manifest(box_model, shifted)

    rep_eng = run_independent_validation(box_model, shifted, manifest)
    rep_run = ValidationRunner().validate(box_model, shifted, manifest)

    assert_validation_parity(rep_eng, rep_run)
    assert rep_eng.status == "REJECTED"
    assert rep_eng.gates["geometry"].status == "FAIL"
    assert rep_eng.element_statuses[box_model.elements[0].entity_key] == "DEVIATED"


def test_parity_missing_solid(box_model):
    """Case 3: Missing emitted solid must be rejected with missing_count=1 by both."""
    fds_text, _ = serialize_fds(box_model)
    missing_fds = re.sub(r"&OBST[^/]+/", "", fds_text)
    manifest = build_manifest(box_model, missing_fds)

    rep_eng = run_independent_validation(box_model, missing_fds, manifest)
    rep_run = ValidationRunner().validate(box_model, missing_fds, manifest)

    assert_validation_parity(rep_eng, rep_run)
    assert rep_eng.status == "REJECTED"
    assert rep_eng.missing_count == 1
    assert rep_eng.element_statuses[box_model.elements[0].entity_key] == "MISSING"


def test_parity_unexpected_primitive(box_model):
    """Case 4: Primitive with unknown provenance must fail traceability in both."""
    fds_text, _ = serialize_fds(box_model)
    tampered_fds = fds_text.replace('"entity_key": "fixture:1"', '"entity_key": "unknown:999"')
    manifest = build_manifest(box_model, tampered_fds)

    rep_eng = run_independent_validation(box_model, tampered_fds, manifest)
    rep_run = ValidationRunner().validate(box_model, tampered_fds, manifest)

    assert_validation_parity(rep_eng, rep_run)
    assert rep_eng.status == "REJECTED"
    assert rep_eng.gates["traceability"].status == "FAIL"


def test_parity_syntax_error(box_model):
    """Case 5: Syntax error in namelist must fail syntax gate in both."""
    fds_text, _ = serialize_fds(box_model)
    bad_syntax = fds_text.replace("&TIME T_END=0.0 /", "&TIME T_END=0.0")
    manifest = build_manifest(box_model, bad_syntax)

    rep_eng = run_independent_validation(box_model, bad_syntax, manifest)
    rep_run = ValidationRunner().validate(box_model, bad_syntax, manifest)

    assert_validation_parity(rep_eng, rep_run)
    assert rep_eng.status == "REJECTED"
    assert rep_eng.gates["syntax"].status == "FAIL"


def test_parity_air_leak_detected(box_model):
    """Case 6: Shrunken wall leaving a leak hole must fail air_path in both."""
    wall_key = box_model.elements[0].entity_key
    # 75% open hole in enclosure
    xb_shrunk = [0.0, 0.5, 0.0, 1.0, 0.0, 3.0]
    fds_leaked = (
        "&HEAD TITLE='test' /\n"
        "&TIME T_END=0.0 /\n"
        "&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n"
        "&SURF ID='CONCRETE', DEFAULT=.TRUE. /\n"
        f"! IFC_SOURCE {{\"entity_key\": \"{wall_key}\"}}\n"
        f"&OBST XB={','.join(map(str, xb_shrunk))}, SURF_ID='CONCRETE' /\n"
        "&TAIL /\n"
    )
    manifest = build_manifest(box_model, fds_leaked)

    rep_eng = run_independent_validation(box_model, fds_leaked, manifest)
    rep_run = ValidationRunner().validate(box_model, fds_leaked, manifest)

    assert_validation_parity(rep_eng, rep_run)
    assert rep_eng.status == "REJECTED"
    assert rep_eng.gates["air_path"].status == "FAIL"


def test_parity_legacy_comments_with_rgb(box_model):
    """Case 7: Legacy comments ! IFC entity ... and &SURF RGB=... must be parsed cleanly."""
    wall_key = box_model.elements[0].entity_key
    wall = box_model.elements[0]
    fds_legacy = (
        "&HEAD CHID='legacy', TITLE='Test legacy' /\n"
        "&TIME T_END=0.0 /\n"
        "&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n"
        "&SURF ID='WALL_COLOR', RGB=185,185,185, DEFAULT=.TRUE. /\n"
        f"! IFC entity #{wall.step_id}; GUID={wall.global_id}\n"
        "&OBST ID='wall_obst', XB=0,2,0,1,0,3, SURF_ID='WALL_COLOR' /\n"
        "&TAIL /\n"
    )
    manifest = build_manifest(box_model, fds_legacy)

    rep_eng = run_independent_validation(box_model, fds_legacy, manifest)
    rep_run = ValidationRunner().validate(box_model, fds_legacy, manifest)

    assert_validation_parity(rep_eng, rep_run)
    assert rep_eng.gates["syntax"].status == "PASS"
    assert rep_eng.element_statuses[wall_key] == "MATCHED"


def test_parity_unauthorized_representation(box_model):
    """Case 8: Emitting a primitive marked REFERENCE_GEOMETRY must fail representation."""
    fds_text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, fds_text)

    # Mutate element simulation_role after serialization to test validator's ability to catch unauthorized emission
    wall = box_model.elements[0]
    wall.simulation_role = "REFERENCE_GEOMETRY"

    rep_eng = run_independent_validation(box_model, fds_text, manifest)
    rep_run = ValidationRunner().validate(box_model, fds_text, manifest)

    assert_validation_parity(rep_eng, rep_run)
    assert rep_eng.status == "REJECTED"
    assert rep_eng.gates["representation"].status == "FAIL"
