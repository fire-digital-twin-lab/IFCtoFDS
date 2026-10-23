"""Adversarial reference revisions; approvals below are test-authored only."""

import copy
import json

import pytest

from ifc_to_fds.domain.contracts import OpeningReference
from ifc_to_fds.modules.fds.api import MappingManifest
from ifc_to_fds.modules.geometry.api import payload_dir, seal, write_package
from ifc_to_fds.modules.reference.api import (
    bundle_digest, create_candidate, golden_gate, inspect_case, registered_cases,
)
from ifc_to_fds.modules.simulation.api import plan_mapping
from ifc_to_fds.modules.verification.contracts import AcceptanceReport
from tests.support.checked_mapping import checked


def review_fixture(directory, **overrides):
    # This is a controlled analytic fixture, never production auto-approval.
    document = dict(status="APPROVED", bundle_sha256=bundle_digest(directory),
                    reviewer="Analytic fixture reviewer", rationale="Known box dimensions",
                    evidence=["Authored fixture specification"])
    document.update(overrides)
    (directory / "approval.json").write_text(json.dumps(document), encoding="utf-8")


@pytest.fixture
def reference(box_model, tmp_path):
    text, manifest, package, report, config = checked(box_model)
    directory = tmp_path / "reference"
    create_candidate(directory, box_model, manifest, package, report, config, text)
    review_fixture(directory)
    return directory, box_model, text, manifest, package, config


@pytest.mark.parametrize("field,value", [
    ("reviewer", "   "), ("reviewer", 17), ("rationale", "\t"),
    ("evidence", "document"), ("evidence", [""]), ("evidence", {"file": "review.pdf"}),
])
def test_malformed_approval_cannot_pass_cli_gate_or_registry(reference, monkeypatch, field, value):
    from ifc_to_fds.interfaces.cli.main import main

    directory, model, text, manifest, package, config = reference
    review_fixture(directory, **{field: value})
    report = AcceptanceReport()
    golden_gate(report, model, manifest, package, {**config, "reference_case": str(directory)}, text)
    gate = report.gates["golden_reference_parity"]
    assert gate.status == "INCONCLUSIVE", gate.reason
    assert gate.evidence["human_approval_verified"] is False
    assert main(["reference-check", str(directory)]) == 2
    monkeypatch.setenv("IFCFDS_REFERENCE_CASES", json.dumps({"analytic": str(directory)}))
    entry = registered_cases()[0]
    assert entry["approval_status"] == "UNVERIFIED_APPROVAL"
    assert entry["integrity_status"] == "VERIFIED"


@pytest.mark.parametrize("mutation", ["sources", "scope", "elements", "ports", "missing_ports", "package_sources", "opening_host"])
def test_cross_file_conflicts_fail_even_after_all_checksums_are_updated(reference, mutation, monkeypatch):
    directory, _, _, manifest, _, _ = reference
    if mutation == "sources":
        name = "sources.json"
        value = json.loads((directory / name).read_text())
        value["sources"][0]["file_hash_sha256"] = "another-source"
    elif mutation == "scope":
        name = "scope.json"
        value = json.loads((directory / name).read_text())
        value["simulation_domain"] = {"xmin": -100, "xmax": 100}
    elif mutation == "opening_host":
        name, value = "openings-reference.json", {"unknown:host": []}
    else:
        name = "geometry-package.json"
        value = json.loads((directory / name).read_text())
        key = manifest.records[0].entity_key
        if mutation == "elements":
            value["elements"].pop(key)
        elif mutation == "ports":
            value["elements"][key]["ports"] = [{"port_key": "unreviewed-port"}]
        elif mutation == "missing_ports":
            value["elements"][key].pop("ports")
        else:
            value["sources"][0]["world_transform"][3] += 1
        value = seal(value)
        # Coherently update the golden manifest's package checksum as well.
        revised = manifest.model_copy(deep=True)
        revised.geometry_package_sha256 = value["sha256"]
        revised.reseal()
        (directory / "golden-manifest.json").write_text(revised.model_dump_json(), encoding="utf-8")
    (directory / name).write_text(json.dumps(value), encoding="utf-8")
    review_fixture(directory)
    with pytest.raises(ValueError, match="conflicts"):
        inspect_case(directory)
    monkeypatch.setenv("IFCFDS_REFERENCE_CASES", json.dumps({"analytic": str(directory)}))
    assert registered_cases()[0]["integrity_status"] == "CORRUPTED"


@pytest.mark.parametrize("mutation", ["global_id", "step_id", "fillings"])
def test_opening_projection_must_match_the_reviewed_inventory(box_model, tmp_path, mutation):
    box_model.elements[0].openings = [OpeningReference(
        opening_step_id=9, opening_global_id="opening-guid", opening_name="Opening",
        filling_global_ids=["door-guid"],
    )]
    plan_mapping(box_model, force_all_geom=True)
    text, manifest, package, report, config = checked(box_model)
    directory = tmp_path / "opening-reference"
    create_candidate(directory, box_model, manifest, package, report, config, text)
    name = directory / "openings-reference.json"
    value = json.loads(name.read_text())
    record = value[box_model.elements[0].entity_key][0]
    record[mutation] = {"global_id": "wrong", "step_id": 100, "fillings": []}[mutation]
    name.write_text(json.dumps(value), encoding="utf-8")
    review_fixture(directory)
    with pytest.raises(ValueError, match="openings-reference.json"):
        inspect_case(directory)


@pytest.mark.parametrize("mutation", ["missing", "corrupted"])
def test_registry_checks_geometry_payload_bytes(box_model, tmp_path, monkeypatch, mutation):
    text, manifest, _, report, config = checked(box_model)
    package = write_package(box_model, tmp_path / "original/geometry.json")
    manifest.geometry_package_sha256 = package["sha256"]
    manifest.reseal()
    directory = tmp_path / "disk-reference"
    create_candidate(directory, box_model, manifest, package, report, config, text)
    review_fixture(directory)
    monkeypatch.setenv("IFCFDS_REFERENCE_CASES", json.dumps({"analytic": str(directory)}))
    assert registered_cases()[0]["integrity_status"] == "VERIFIED"
    payload = next(payload_dir(directory / "geometry-package.json").glob("*.bin"))
    if mutation == "missing":
        payload.unlink()
    else:
        data = bytearray(payload.read_bytes())
        data[-1] ^= 1
        payload.write_bytes(data)
    entry = registered_cases()[0]
    assert entry["integrity_status"] == "CORRUPTED"
    assert entry["approval_status"] == "UNVERIFIED_CORRUPT"


@pytest.mark.parametrize("changes", ["not-a-list", [None], ["not-a-change"], [{"entity_key": "fixture:1"}]])
def test_invalid_delta_document_yields_a_finding_instead_of_crashing(reference, changes):
    directory, model, text, manifest, package, config = reference
    report = AcceptanceReport()
    golden_gate(report, model, manifest, package, {
        **config, "reference_case": str(directory),
        "intentional_deltas": {"status": "APPROVED", "reference_digest": bundle_digest(directory),
                               "changes": copy.deepcopy(changes)},
    }, text)
    assert report.gates["golden_reference_parity"].status == "FAIL"
    assert any("delta" in finding.title for finding in report.findings)


@pytest.mark.parametrize("key", [[], {"invalid": "identity"}])
def test_invalid_delta_identity_is_a_finding(reference, key):
    directory, model, text, manifest, package, config = reference
    report = AcceptanceReport()
    change = dict(entity_key=key, field="name", before="Wall", after="Edited",
                  reviewer="Fixture reviewer", rationale="Invalid identity test", evidence=["test"])
    golden_gate(report, model, manifest, package, {
        **config, "reference_case": str(directory),
        "intentional_deltas": dict(status="APPROVED", reference_digest=bundle_digest(directory), changes=[change]),
    }, text)
    assert report.gates["golden_reference_parity"].status == "FAIL"


@pytest.mark.parametrize("key", [[], {"invalid": "identity"}])
def test_invalid_alias_identity_is_a_finding(reference, key):
    directory, model, text, manifest, package, config = reference
    alias = dict(entity_key=key, geometry_entity_key="fixture:1", reviewer="Fixture reviewer",
                 rationale="Invalid identity test", evidence=["test"])
    (directory / "alias-decisions.json").write_text(json.dumps([alias]), encoding="utf-8")
    review_fixture(directory)
    report = AcceptanceReport()
    golden_gate(report, model, manifest, package, {**config, "reference_case": str(directory)}, text)
    assert report.gates["golden_reference_parity"].status == "FAIL"


@pytest.mark.parametrize("status", ["DRAFT", "SUPERSEDED"])
def test_reference_check_positive_and_unapproved_status(reference, status):
    from ifc_to_fds.interfaces.cli.main import main

    directory, model, text, manifest, package, config = reference
    assert main(["reference-check", str(directory)]) == 0
    review_fixture(directory, status=status)
    assert main(["reference-check", str(directory)]) == 2
    report = AcceptanceReport()
    golden_gate(report, model, manifest, package, {**config, "reference_case": str(directory)}, text)
    assert report.gates["golden_reference_parity"].status == "INCONCLUSIVE"


@pytest.mark.parametrize("name,value", [("approval.json", []), ("scope.json", []), ("alias-decisions.json", [17])])
def test_malformed_document_shape_has_a_controlled_integrity_error(reference, name, value):
    directory, *_ = reference
    (directory / name).write_text(json.dumps(value), encoding="utf-8")
    if name != "approval.json":
        review_fixture(directory)
    with pytest.raises(ValueError, match="Invalid reference"):
        inspect_case(directory)


def test_bad_registry_entry_does_not_hide_a_valid_case(reference, monkeypatch):
    directory, *_ = reference
    monkeypatch.setenv("IFCFDS_REFERENCE_CASES", json.dumps({"broken": 17, "valid": str(directory)}))
    entries = {entry["id"]: entry for entry in registered_cases()}
    assert entries["broken"]["integrity_status"] == "UNAVAILABLE"
    assert entries["valid"]["integrity_status"] == "VERIFIED"
    assert entries["valid"]["human_approval_verified"] is True


def test_reference_audit_reopens_saved_source_and_output(tiny_ifc, tmp_path):
    from ifc_to_fds.pipeline import audit, convert, prepare, save_artifacts
    from ifc_to_fds.modules.geometry.api import read_package

    source, _, _ = tiny_ifc
    result = convert([source], output_directory=tmp_path / "conversion")
    fds = tmp_path / "saved.fds"
    save_artifacts(result, fds)
    text = fds.read_text(encoding="utf-8")
    manifest = MappingManifest.model_validate_json((tmp_path / "saved_manifest.json").read_text())
    package = read_package(tmp_path / "saved_geometry.json")
    model = prepare([source], result["configuration"], reference=True)
    directory = tmp_path / "independent-reference"
    create_candidate(directory, model, manifest, package,
                     AcceptanceReport.model_validate(result["report"]), result["configuration"], text)
    config = {**result["configuration"], "reference_case": str(directory)}
    _, _, draft = audit([source], text, manifest, config, package)
    assert draft.gates["golden_reference_parity"].status == "INCONCLUSIVE"
    review_fixture(directory)
    _, _, accepted = audit([source], text, manifest, config, package)
    assert accepted.gates["golden_reference_parity"].status == "PASS", accepted.model_dump()
    assert accepted.mapping_status == "MAPPING_VERIFIED"
    # Change the saved FDS and reseal its manifest. The approved reference and
    # source are preserved, and a fresh audit must still reject this deviation.
    altered = text.replace("XB=0,2,0,1,0,3, SURF_ID", "XB=0.01,2.01,0,1,0,3, SURF_ID")
    assert altered != text
    import hashlib
    manifest.fds_sha256 = hashlib.sha256(altered.encode()).hexdigest()
    manifest.reseal()
    fds.write_text(altered, encoding="utf-8")
    _, _, rejected = audit([source], fds.read_text(encoding="utf-8"), manifest, config, package)
    assert rejected.gates["golden_reference_parity"].status == "FAIL"
    assert rejected.mapping_status == "REJECTED"
