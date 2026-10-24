"""Comprehensive test suite for Feature 6: Golden Reference Governance, Projection Completeness & Scientific Reproducibility.

Covers:
- F01: Approval provenance: separation of data integrity verification from human approval.
- F02: Reverse projection coverage contract: omitting required elements from projection files fails validation.
- F03: Full mapping ledger parity: mapping_strategy and fds_primitive_ids captured in snapshot FIELDS.
- F05: Execution provenance capturing runtime environment versions.
- F06: Portable evidence: reference_case sanitizes local machine filesystem paths.
- F08: UI integrity: registered_cases verifies bundle checksum before reporting approval status.
"""

import copy
import json
import pytest

from ifc_to_fds.adapters.reference import FilesystemReferenceRepository
from ifc_to_fds.core import get_execution_provenance
from ifc_to_fds.geometry.package import build_package
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.results import registered_cases
from ifc_to_fds.validation.acceptance import AcceptanceReport, GateStatus
from ifc_to_fds.validation.golden import bundle_digest, create_candidate, golden_gate
from ifc_to_fds.validation.reference_integrity import FIELDS, validate_reference


def test_full_mapping_ledger_in_fields():
    """F03: FIELDS must include mapping_strategy and fds_primitive_ids for ledger parity."""
    assert "mapping_strategy" in FIELDS
    assert "fds_primitive_ids" in FIELDS


def test_execution_provenance_captured():
    """F05: Runtime execution provenance captures environment fingerprint."""
    prov = get_execution_provenance()
    assert "python_version" in prov
    assert "platform" in prov
    assert "system" in prov
    assert "machine" in prov
    assert "ifcopenshell_version" in prov or "trimesh_version" in prov


def test_portable_evidence_sanitizes_local_paths(box_model, tmp_path):
    """F06: golden_gate evidence must not leak local machine absolute paths."""
    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "reference_case_vault"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    # Approve test fixture
    (ref_dir / "approval.json").write_text(
        json.dumps({
            "status": "APPROVED",
            "bundle_sha256": bundle_digest(ref_dir),
            "reviewer": "Safety Auditor",
            "rationale": "Analytic reference test",
            "evidence": ["Doc-101"],
        }),
        encoding="utf-8",
    )

    # Evaluate golden gate passing the absolute local path
    config = {"reference_case": str(ref_dir.resolve())}
    golden_gate(report, box_model, manifest, package, config, text)

    gate = report.gates["golden_reference_parity"]
    ref_case_evidence = gate.evidence.get("reference_case", "")

    # Must be sanitized to directory name, without drive letters or directory separators
    assert ref_case_evidence == "reference_case_vault"
    assert "\\" not in ref_case_evidence
    assert "/" not in ref_case_evidence
    assert gate.evidence.get("data_integrity_verified") is True
    assert gate.evidence.get("human_approval_verified") is True


def test_reverse_projection_coverage_detects_omission(box_model, tmp_path):
    """F02: Omitting an element from any projection file must fail reverse coverage validation."""
    from ifc_to_fds.core.canonical import MappingStrategy, ScopeDecision

    # Add an excluded element to box_model so create_candidate populates exclusions.json
    wall = box_model.elements[0]
    excluded_elem = wall.model_copy(deep=True)
    excluded_elem.entity_key = "fixture:excluded_wall"
    excluded_elem.step_id = 999
    excluded_elem.global_id = "guid-excluded-999"
    excluded_elem.mapping_strategy = MappingStrategy.EXCLUDED_SCOPE
    excluded_elem.scope_decision = ScopeDecision.OUT_OF_SCOPE
    excluded_elem.fds_representation = "NONE"
    box_model.elements.append(excluded_elem)
    plan_mapping(box_model)

    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "ref_bundle"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    repo = FilesystemReferenceRepository()
    _, _, files = repo.inspect_case(ref_dir)

    # exclusions.json initially has fixture:excluded_wall
    assert "fixture:excluded_wall" in files["exclusions.json"]

    # Corrupt reverse coverage: delete fixture:excluded_wall from exclusions.json
    corrupted_files = copy.deepcopy(files)
    del corrupted_files["exclusions.json"]["fixture:excluded_wall"]

    # Must fail reverse coverage with incomplete exclusions.json!
    with pytest.raises(ValueError, match="Reference projection coverage incomplete: exclusions.json"):
        validate_reference(corrupted_files)


def test_reverse_projection_coverage_detects_missing_hvac(box_model, tmp_path):
    """NEW-02: Missing HVAC element from hvac-reference.json fails reverse coverage check."""
    from ifc_to_fds.core.canonical import MEPSystem
    wall = box_model.elements[0]
    duct = wall.model_copy(deep=True)
    duct.entity_key = "fixture:duct_1"
    duct.step_id = 888
    duct.global_id = "guid-duct-888"
    duct.ifc_type = "IfcDuctSegment"
    duct.mep_category = "VENTILATION"
    duct.system_ids = ["sys_hvac_1"]
    box_model.elements.append(duct)
    box_model.mep_graph.systems.append(
        MEPSystem(system_id="sys_hvac_1", name="Supply Air", system_type="VENTILATION")
    )
    plan_mapping(box_model)

    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "ref_bundle_hvac"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    repo = FilesystemReferenceRepository()
    _, _, files = repo.inspect_case(ref_dir)

    assert "fixture:duct_1" in files["hvac-reference.json"]

    # Delete duct from hvac-reference.json
    corrupted_files = copy.deepcopy(files)
    del corrupted_files["hvac-reference.json"]["fixture:duct_1"]

    with pytest.raises(ValueError, match="Reference projection coverage incomplete: hvac-reference.json"):
        validate_reference(corrupted_files)


def test_reverse_projection_coverage_detects_missing_fire_protection(box_model, tmp_path):
    """NEW-02: Missing fire suppression pipe from fire-protection-reference.json fails reverse coverage check."""
    from ifc_to_fds.core.canonical import MEPSystem
    wall = box_model.elements[0]
    pipe = wall.model_copy(deep=True)
    pipe.entity_key = "fixture:pipe_1"
    pipe.step_id = 777
    pipe.global_id = "guid-pipe-777"
    pipe.ifc_type = "IfcPipeSegment"
    pipe.mep_category = "FIRE_SUPPRESSION"
    pipe.system_ids = ["sys_fp_1"]
    box_model.elements.append(pipe)
    box_model.mep_graph.systems.append(
        MEPSystem(system_id="sys_fp_1", name="Sprinkler", system_type="FIRE_SUPPRESSION")
    )
    plan_mapping(box_model)

    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "ref_bundle_fp"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    repo = FilesystemReferenceRepository()
    _, _, files = repo.inspect_case(ref_dir)

    assert "fixture:pipe_1" in files["fire-protection-reference.json"]

    # Delete pipe from fire-protection-reference.json
    corrupted_files = copy.deepcopy(files)
    del corrupted_files["fire-protection-reference.json"]["fixture:pipe_1"]

    with pytest.raises(ValueError, match="Reference projection coverage incomplete: fire-protection-reference.json"):
        validate_reference(corrupted_files)


def _set_system_ids(files, entity_key, system_ids):
    """Test helper: set system_ids for one element consistently across every
    file that carries its record, so manifest/inventory/projection parity holds
    and only the mep-reference linkage under test varies."""
    files["expected-inventory.json"][entity_key]["system_ids"] = list(system_ids)
    for rec in files["golden-manifest.json"]["records"]:
        if rec["entity_key"] == entity_key:
            rec["system_ids"] = list(system_ids)
    for payload in files.values():
        if isinstance(payload, dict) and entity_key in payload:
            entry = payload[entity_key]
            if isinstance(entry, dict) and "system_ids" in entry:
                entry["system_ids"] = list(system_ids)


def test_unknown_system_id_fails_reference_validation(box_model, tmp_path):
    """A2: system_ids absent from mep-reference.json must fail closed, not be silently filtered."""
    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "ref_bundle_unknown_sys"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    repo = FilesystemReferenceRepository()
    _, _, files = repo.inspect_case(ref_dir)

    corrupted_files = copy.deepcopy(files)
    _set_system_ids(corrupted_files, "fixture:1", ["UNKNOWN-SYS"])
    assert all(
        s.get("system_id") != "UNKNOWN-SYS"
        for s in corrupted_files["mep-reference.json"].get("systems", [])
    )

    with pytest.raises(ValueError, match="unknown system_id"):
        validate_reference(corrupted_files)


def test_known_system_id_passes_reference_validation(box_model, tmp_path):
    """A2 regression: system_ids present in mep-reference.json must keep validating."""
    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "ref_bundle_known_sys"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    repo = FilesystemReferenceRepository()
    _, _, files = repo.inspect_case(ref_dir)

    known_files = copy.deepcopy(files)
    _set_system_ids(known_files, "fixture:1", ["sys_known_1"])
    known_files["mep-reference.json"].setdefault("systems", []).append(
        {"system_id": "sys_known_1", "name": "Known", "system_type": "PLUMBING"}
    )

    validate_reference(known_files)  # must not raise


def test_registered_cases_detects_tampered_bundle_checksum(tmp_path, monkeypatch):
    """F08: registered_cases verifies bundle checksum and flags tampered bundles as CORRUPTED."""
    case_dir = tmp_path / "test_ref_case"
    case_dir.mkdir(parents=True, exist_ok=True)

    # Write dummy reference files
    (case_dir / "sources.json").write_text(
        json.dumps({"sources": [{"file_hash_sha256": "hash_123"}]}), encoding="utf-8"
    )
    # Write approval claiming APPROVED with a forged bundle_sha256
    (case_dir / "approval.json").write_text(
        json.dumps({
            "status": "APPROVED",
            "bundle_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            "reviewer": "Alice",
        }),
        encoding="utf-8",
    )

    # Register case via env
    registered_config = {
        "case_test": {
            "name": "Tampered Reference Case",
            "path": str(case_dir),
        }
    }
    monkeypatch.setenv("IFCFDS_REFERENCE_CASES", json.dumps(registered_config))

    cases = registered_cases()
    assert len(cases) == 1
    case_entry = cases[0]

    # Must detect mismatch: integrity_status must be CORRUPTED, approval_status UNVERIFIED_CORRUPT
    assert case_entry["integrity_status"] == "CORRUPTED"
    assert case_entry["approval_status"] == "UNVERIFIED_CORRUPT"


def test_draft_reference_evaluates_inconclusive_not_pass(box_model, tmp_path):
    """F01: Reference in DRAFT status must evaluate to INCONCLUSIVE even with valid data integrity."""
    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "draft_ref"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    # Retain status DRAFT in approval.json
    (ref_dir / "approval.json").write_text(
        json.dumps({
            "status": "DRAFT",
            "bundle_sha256": bundle_digest(ref_dir),
            "reviewer": None,
            "rationale": None,
            "evidence": None,
        }),
        encoding="utf-8",
    )

    config = {"reference_case": str(ref_dir)}
    golden_gate(report, box_model, manifest, package, config, text)

    gate = report.gates["golden_reference_parity"]
    assert gate.status == GateStatus.INCONCLUSIVE
    assert "DRAFT" in gate.reason
    assert gate.evidence.get("data_integrity_verified") is True
    assert gate.evidence.get("human_approval_verified") is False


def test_system_entry_missing_system_id_fails_closed(box_model, tmp_path):
    """P1: mep-reference system entry without system_id must fail closed with
    ValueError, not escape as KeyError."""
    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "ref_bundle_missing_sysid"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    repo = FilesystemReferenceRepository()
    _, _, files = repo.inspect_case(ref_dir)

    corrupted_files = copy.deepcopy(files)
    corrupted_files["mep-reference.json"]["systems"] = [{"name": "NoId"}]

    with pytest.raises(ValueError, match="system entry missing system_id"):
        validate_reference(corrupted_files)


def test_null_system_ids_does_not_raise_type_error(box_model, tmp_path):
    """P1: inventory element with system_ids null must fail closed with
    ValueError, never escape as TypeError."""
    text, _ = serialize_fds(box_model)
    package = build_package(box_model)
    manifest = build_manifest(box_model, text)
    report = AcceptanceReport()

    ref_dir = tmp_path / "ref_bundle_null_sysids"
    create_candidate(ref_dir, box_model, manifest, package, report, {}, text)

    repo = FilesystemReferenceRepository()
    _, _, files = repo.inspect_case(ref_dir)

    corrupted_files = copy.deepcopy(files)
    corrupted_files["expected-inventory.json"]["fixture:1"]["system_ids"] = None

    with pytest.raises(ValueError):
        validate_reference(corrupted_files)  # must not raise TypeError
