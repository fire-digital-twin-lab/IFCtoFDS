"""Mutation testing suite for independent validation and traceability (T01-T07).

Validates that all six intentional mutation modes (T02-T07) are reliably detected
and rejected by both the production validation engine and the modular runner:
- T01: Clean baseline (not mutated)
- T02: Geometry shift mutation (translated XB)
- T03: Primitive omission / missing solid mutation (deleted &OBST)
- T04: Provenance tampering mutation (corrupted entity_key)
- T05: Void omission / resealed opening mutation
- T06: Air leak / compartment breach mutation (shrunk enclosure wall)
- T07: Computational domain mismatch mutation (differing &MESH XB)
"""

import re
import trimesh
from ifc_to_fds.core.canonical import BoundingBox, OpeningReference, TriangleMesh
from ifc_to_fds.geometry.mesh import as_trimesh, box_mesh
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.validation.acceptance import AcceptanceStatus, GateStatus, Severity
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.runner import ValidationRunner


def audit_both(model, fds_text, manifest, config=None):
    """Runs both validation engines and returns their reports."""
    rep_eng = run_independent_validation(model, fds_text, manifest, config=config)
    rep_run = ValidationRunner().validate(model, fds_text, manifest, config=config)
    return rep_eng, rep_run


def test_t01_clean_baseline(box_model):
    """T01: Clean baseline without mutations passes verification."""
    fds_text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, fds_text)

    rep_eng, rep_run = audit_both(box_model, fds_text, manifest)

    assert rep_eng.status != AcceptanceStatus.REJECTED
    assert rep_run.status != AcceptanceStatus.REJECTED
    assert rep_eng.gates["geometry"].status == GateStatus.PASS
    assert rep_run.gates["geometry"].status == GateStatus.PASS
    assert rep_eng.gates["traceability"].status == GateStatus.PASS
    assert rep_run.gates["traceability"].status == GateStatus.PASS
    assert rep_eng.missing_count == 0
    assert rep_run.missing_count == 0


def test_t02_geometry_shift_mutation(box_model):
    """T02: Shifting coordinates of an obstacle must fail geometry gate and reject."""
    wall_key = box_model.elements[0].entity_key
    fds_text, _ = serialize_fds(box_model)
    # Translate XB coordinates by +0.5m
    shifted_fds = fds_text.replace("XB=0,2,0,1,0,3", "XB=0.5000,2.5000,0.0000,1.0000,0.0000,3.0000")
    manifest = build_manifest(box_model, shifted_fds)

    rep_eng, rep_run = audit_both(box_model, shifted_fds, manifest)

    assert rep_eng.status == AcceptanceStatus.REJECTED
    assert rep_run.status == AcceptanceStatus.REJECTED
    assert rep_eng.gates["geometry"].status == GateStatus.FAIL
    assert rep_run.gates["geometry"].status == GateStatus.FAIL
    assert rep_eng.element_statuses[wall_key] == "DEVIATED"
    assert rep_run.element_statuses[wall_key] == "DEVIATED"
    assert any(f.category == "geometry" and f.severity == Severity.P1 for f in rep_eng.findings)


def test_t03_missing_solid_mutation(box_model):
    """T03: Deleting an emitted solid must report missing_count=1 and reject."""
    wall_key = box_model.elements[0].entity_key
    fds_text, _ = serialize_fds(box_model)
    # Remove the entire &OBST block
    missing_fds = re.sub(r"&OBST[^/]+/", "", fds_text)
    manifest = build_manifest(box_model, missing_fds)

    rep_eng, rep_run = audit_both(box_model, missing_fds, manifest)

    assert rep_eng.status == AcceptanceStatus.REJECTED
    assert rep_run.status == AcceptanceStatus.REJECTED
    assert rep_eng.missing_count == 1
    assert rep_run.missing_count == 1
    assert rep_eng.element_statuses[wall_key] == "MISSING"
    assert rep_run.element_statuses[wall_key] == "MISSING"
    assert rep_eng.gates["traceability"].status == GateStatus.FAIL
    assert rep_run.gates["traceability"].status == GateStatus.FAIL
    assert any(f.severity == Severity.P0 and f.element_id == wall_key for f in rep_eng.findings)


def test_t04_provenance_tampering_mutation(box_model):
    """T04: Corrupted or forged provenance metadata must fail traceability."""
    fds_text, _ = serialize_fds(box_model)
    # Tamper entity_key in the IFC_SOURCE comment
    tampered_fds = fds_text.replace('"entity_key": "fixture:1"', '"entity_key": "forged:9999"')
    manifest = build_manifest(box_model, tampered_fds)

    rep_eng, rep_run = audit_both(box_model, tampered_fds, manifest)

    assert rep_eng.status == AcceptanceStatus.REJECTED
    assert rep_run.status == AcceptanceStatus.REJECTED
    assert rep_eng.gates["traceability"].status == GateStatus.FAIL
    assert rep_run.gates["traceability"].status == GateStatus.FAIL
    assert any(f.category == "traceability" and f.severity == Severity.P0 for f in rep_eng.findings)


def test_t05_void_omission_mutation(box_model):
    """T05: Resealing a wall opening or omitting a required void must fail openings gate."""
    wall = box_model.elements[0]
    solid = wall.mesh.model_copy(deep=True)
    opening_bbox = BoundingBox(xmin=0.5, xmax=1.5, ymin=-0.1, ymax=1.1, zmin=0.5, zmax=2.0)
    opening = box_mesh(opening_bbox)

    cut = trimesh.boolean.difference([as_trimesh(solid), as_trimesh(opening)], engine="manifold")
    wall.mesh = TriangleMesh(vertices=cut.vertices.tolist(), faces=cut.faces.tolist())
    wall.openings = [
        OpeningReference(
            opening_global_id="void-door-guid",
            opening_step_id=99,
            opening_name="DoorVoid",
            mesh=opening,
        )
    ]
    plan_mapping(box_model, force_all_geom=True)

    # Mutant: emit the original uncarved solid (resealed void)
    mutant_model = box_model.model_copy(deep=True)
    mutant_model.elements[0].mesh = solid
    resealed_fds, _ = serialize_fds(mutant_model)
    manifest = build_manifest(box_model, resealed_fds)

    rep_eng, rep_run = audit_both(box_model, resealed_fds, manifest)

    assert rep_eng.status == AcceptanceStatus.REJECTED
    assert rep_run.status == AcceptanceStatus.REJECTED
    assert rep_eng.gates["openings"].status == GateStatus.FAIL
    assert rep_run.gates["openings"].status == GateStatus.FAIL
    assert any(f.category == "openings" and f.severity == Severity.P1 for f in rep_eng.findings)


def test_t06_air_leak_mutation(box_model):
    """T06: Compartmentation breach leaving envelope air leak must fail air_path gate."""
    wall_key = box_model.elements[0].entity_key
    # Shrink wall leaving a 75% wide gap
    xb_shrunk = [0.0, 0.5, 0.0, 1.0, 0.0, 3.0]
    leaked_fds = (
        "&HEAD TITLE='leaked_test' /\n"
        "&TIME T_END=0.0 /\n"
        "&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n"
        "&SURF ID='CONCRETE', DEFAULT=.TRUE. /\n"
        f"! IFC_SOURCE {{\"entity_key\": \"{wall_key}\"}}\n"
        f"&OBST XB={','.join(map(str, xb_shrunk))}, SURF_ID='CONCRETE' /\n"
        "&TAIL /\n"
    )
    manifest = build_manifest(box_model, leaked_fds)

    rep_eng, rep_run = audit_both(box_model, leaked_fds, manifest)

    assert rep_eng.status == AcceptanceStatus.REJECTED
    assert rep_run.status == AcceptanceStatus.REJECTED
    assert rep_eng.gates["air_path"].status == GateStatus.FAIL
    assert rep_run.gates["air_path"].status == GateStatus.FAIL
    assert any(f.category == "air_path" and f.severity == Severity.P1 for f in rep_eng.findings)


def test_t07_domain_mismatch_mutation(box_model):
    """T07: MESH XB differing from declared simulation_domain must fail domain gate."""
    box_model.simulation_domain = BoundingBox(xmin=0.0, xmax=2.0, ymin=0.0, ymax=1.0, zmin=0.0, zmax=3.0)
    fds_text, _ = serialize_fds(box_model)
    # Alter &MESH XB so it disagrees with simulation domain
    tampered_domain_fds = fds_text.replace("XB=0,2,0,1,0,3", "XB=1.0000,3.0000,0.0000,1.0000,0.0000,3.0000")
    manifest = build_manifest(box_model, tampered_domain_fds)

    rep_eng, rep_run = audit_both(box_model, tampered_domain_fds, manifest)

    assert rep_eng.status == AcceptanceStatus.REJECTED
    assert rep_run.status == AcceptanceStatus.REJECTED
    assert rep_eng.gates["domain"].status == GateStatus.FAIL
    assert rep_run.gates["domain"].status == GateStatus.FAIL
    assert any(f.category == "domain" for f in rep_eng.findings)
