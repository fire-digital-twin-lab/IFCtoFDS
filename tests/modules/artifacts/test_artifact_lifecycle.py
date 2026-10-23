"""Comprehensive test suite for Feature 3: Artifact Lifecycle, MappingBundle Integrity, and Persistence.

Covers:
- F01: bundle_sha256 sensitivity to records, reverse primitive mapping, and multi-sources.
- F02: Atomic artifact persistence via staging directory pattern.
- F03: Checksum isolation without wildcard glob collisions.
- F04: Checkpoint manifest resealing with geometry_package hash.
- F05: Portable metadata: sanitization of local machine paths in inventory.
- F06: Geometry package archive restoration with integrity checks and Zip-slip prevention.
- F07: CLI support for profile 'geometry-fidelity'.
"""

import copy
import json
import zipfile
from pathlib import Path
import pytest
from ifc_to_fds.adapters.storage.filesystem import LocalFilesystemArtifactRepository
from ifc_to_fds.cli import main as cli_main
from ifc_to_fds.geometry.storage import archive_package, restore_package, write_package
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.pipeline import convert, save_artifacts


def test_bundle_sha256_records_sensitivity(box_model):
    """F01: Modifying any element mapping record must change bundle_sha256."""
    fds_text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, fds_text)
    hash_original = manifest.bundle_sha256
    assert hash_original and len(hash_original) == 64

    # 1. Mutate simulation_role
    record = manifest.records[0]
    record.simulation_role = "REFERENCE_GEOMETRY"
    hash_after_role = manifest.compute_bundle_sha256()
    assert hash_after_role != hash_original

    # 2. Mutate mapping_strategy
    record.mapping_strategy = "GEOM"
    hash_after_strategy = manifest.compute_bundle_sha256()
    assert hash_after_strategy != hash_after_role

    # 3. Mutate primitive ownership
    record.fds_primitive_ids = ["PRIMITIVE_TAMPERED"]
    hash_after_prims = manifest.compute_bundle_sha256()
    assert hash_after_prims != hash_after_strategy

    # 4. Reseal updates manifest attribute
    new_hash = manifest.reseal()
    assert new_hash == hash_after_prims
    assert manifest.bundle_sha256 == new_hash


def test_bundle_sha256_expanded_fields_sensitivity(box_model):
    """NEW-09: Mutating boundary_treatment, simulation_domain, or system_ids changes bundle_sha256."""
    fds_text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, fds_text)
    base_hash = manifest.bundle_sha256

    # Mutate boundary_treatment
    manifest.records[0].boundary_treatment = "PENDING_VALIDATION"
    hash1 = manifest.compute_bundle_sha256()
    assert hash1 != base_hash

    # Mutate system_ids
    manifest.records[0].system_ids = ["sys_test_1"]
    hash2 = manifest.compute_bundle_sha256()
    assert hash2 != hash1

    # Mutate simulation_domain
    manifest.simulation_domain = {"xmin": -10, "xmax": 10, "ymin": -10, "ymax": 10, "zmin": -10, "zmax": 10}
    hash3 = manifest.compute_bundle_sha256()
    assert hash3 != hash2


def test_bundle_sha256_multi_source_sensitivity(box_model):
    """F01: Modifying secondary source checksum in federated models must change bundle_sha256."""
    fds_text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, fds_text)

    # Attach two sources
    manifest.sources = [
        {"source_id": "src_1", "file_hash_sha256": "hash_111"},
        {"source_id": "src_2", "file_hash_sha256": "hash_222"},
    ]
    hash_base = manifest.reseal()

    # Tamper secondary source hash
    manifest.sources[1]["file_hash_sha256"] = "hash_TAMPERED"
    hash_tampered = manifest.compute_bundle_sha256()
    assert hash_tampered != hash_base


def test_bundle_sha256_primitive_reverse_mapping_sensitivity(box_model):
    """F01: Modifying primitive_to_ifc reverse index must change bundle_sha256."""
    fds_text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, fds_text)
    hash_base = manifest.bundle_sha256

    manifest.primitive_to_ifc["UNKNOWN_PRIMITIVE"] = ["fixture:999"]
    hash_modified = manifest.compute_bundle_sha256()
    assert hash_modified != hash_base


def test_atomic_staging_persistence_success(tiny_ifc, tmp_path):
    """F02: Artifact persistence writes all files cleanly and removes temporary staging directory."""
    result = convert([tiny_ifc[0]], output_directory=tmp_path)
    output_fds = tmp_path / "model.fds"
    checksums = save_artifacts(result, output_fds)

    # Verify all expected artifacts exist in target directory
    base_name = output_fds.stem
    expected_files = [
        "model.fds",
        f"{base_name}_manifest.json",
        f"{base_name}_acceptance_report.json",
        f"{base_name}_inventory.json",
        f"{base_name}_mep_graph.json",
        f"{base_name}_configuration.json",
        f"{base_name}_timings.json",
        f"{base_name}_parity.json",
        f"{base_name}_manifest.csv",
        f"{base_name}_acceptance_report.md",
        f"{base_name}_geometry.json",
        f"{base_name}_geometry.zip",
        f"{base_name}_checksums.json",
    ]
    for fname in expected_files:
        assert (tmp_path / fname).is_file(), f"Missing expected artifact: {fname}"

    # Verify no staging directories remain in tmp_path
    staging_dirs = list(tmp_path.glob(".staging-*"))
    assert not staging_dirs, f"Uncleaned staging directories found: {staging_dirs}"

    # Checksums content verification
    assert len(checksums) == 12  # 12 artifacts excluding _checksums.json itself
    for fname, sha in checksums.items():
        assert len(sha) == 64


def test_atomic_staging_persistence_failure_cleanup(tiny_ifc, tmp_path, monkeypatch):
    """F02: On write failure, staging directory is wiped and no partial artifacts are published."""
    result = convert([tiny_ifc[0]])
    target_dir = tmp_path / "target"
    output_fds = target_dir / "model.fds"

    repo = LocalFilesystemArtifactRepository()

    # Simulate an error during artifact writing (e.g. failure in archive_package)
    def fail_archive(*args, **kwargs):
        _ = (args, kwargs)
        raise IOError("Disk write simulation error")

    monkeypatch.setattr("ifc_to_fds.adapters.storage.filesystem.archive_package", fail_archive)

    with pytest.raises(IOError, match="Disk write simulation error"):
        repo.save_run_artifacts(result, output_fds)

    # Target directory should not contain completed model.fds or checksums
    assert not output_fds.exists()
    assert not (target_dir / "model_checksums.json").exists()

    # Staging directory must be cleaned up
    staging_dirs = list(target_dir.glob(".staging-*"))
    assert not staging_dirs


def test_atomic_publication_rollback_on_failure(tiny_ifc, tmp_path, monkeypatch):
    """NEW-03: On failure during publication loop, pre-existing files are restored intact."""
    result = convert([tiny_ifc[0]])
    target_dir = tmp_path / "target"
    target_dir.mkdir(parents=True, exist_ok=True)
    output_fds = target_dir / "model.fds"

    repo = LocalFilesystemArtifactRepository()
    # 1. Initial successful publication
    repo.save_run_artifacts(result, output_fds)
    original_fds = output_fds.read_text(encoding="utf-8")
    original_manifest = (target_dir / "model_manifest.json").read_text(encoding="utf-8")

    # 2. Modify result so it has different FDS text
    mutated_result = copy.deepcopy(result)
    mutated_result["fds_text"] = "&HEAD TITLE='NEW_RUN' /\n"

    # 3. Simulate failure during the replace() loop after replacing the first file
    real_replace = Path.replace
    call_count = 0

    def failing_replace(self, target):
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            raise IOError("Simulated disk error during replacement loop")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)

    with pytest.raises(IOError, match="Simulated disk error during replacement loop"):
        repo.save_run_artifacts(mutated_result, output_fds)

    # 4. Verify rollback: original files must be restored completely!
    assert output_fds.read_text(encoding="utf-8") == original_fds
    assert (target_dir / "model_manifest.json").read_text(encoding="utf-8") == original_manifest

    # 5. Backup directory and staging directory must be cleaned up
    assert not list(target_dir.glob(".backup-*"))
    assert not list(target_dir.glob(".staging-*"))


def test_checksums_glob_isolation(tiny_ifc, tmp_path):
    """F03: Checksums must only contain files emitted in the current run, ignoring prefix collisions."""
    # Pre-create files that share the prefix 'model'
    unrelated_json = tmp_path / "model_unrelated.json"
    unrelated_json.write_text("{}", encoding="utf-8")
    other_fds = tmp_path / "model2.fds"
    other_fds.write_text("&HEAD /", encoding="utf-8")
    legacy_log = tmp_path / "model_old.log"
    legacy_log.write_text("log", encoding="utf-8")

    result = convert([tiny_ifc[0]], output_directory=tmp_path)
    checksums = save_artifacts(result, tmp_path / "model.fds")

    # Read generated checksums.json
    checksums_file = tmp_path / "model_checksums.json"
    recorded = json.loads(checksums_file.read_text(encoding="utf-8"))

    # Verify pre-existing foreign files are NOT captured
    assert "model_unrelated.json" not in recorded
    assert "model2.fds" not in recorded
    assert "model_old.log" not in recorded
    assert "model_unrelated.json" not in checksums
    assert "model2.fds" not in checksums


def test_checkpoint_manifest_resealing(tiny_ifc, tmp_path):
    """F04: Checkpoint manifest must be resealed with valid geometry package hash."""
    convert([tiny_ifc[0]], output_directory=tmp_path)
    checkpoint_manifest_path = tmp_path / "model_manifest.json"
    assert checkpoint_manifest_path.is_file()

    from ifc_to_fds.domain.mapping import MappingManifest

    manifest = MappingManifest.model_validate_json(checkpoint_manifest_path.read_text(encoding="utf-8"))

    # geometry_package_sha256 must be populated
    assert manifest.geometry_package_sha256
    assert len(manifest.geometry_package_sha256) == 64

    # bundle_sha256 must reflect the resealed state
    assert manifest.bundle_sha256 == manifest.compute_bundle_sha256()

    # audit-state.json must record checkpoint status
    audit_state = json.loads((tmp_path / "audit-state.json").read_text(encoding="utf-8"))
    assert audit_state.get("checkpoint_status") in ("DRAFT_NOT_SEALED", "VERIFIED_SEALED")
    assert audit_state.get("bundle_sha256") == manifest.bundle_sha256


def test_inventory_sanitization_removes_local_paths(tiny_ifc, tmp_path):
    """F05: Inventory artifact must not leak absolute local machine file paths."""
    result = convert([tiny_ifc[0]], output_directory=tmp_path)
    save_artifacts(result, tmp_path / "model.fds")

    # Inspect the saved inventory JSON
    inv_path = tmp_path / "model_inventory.json"
    inv_data = json.loads(inv_path.read_text(encoding="utf-8"))

    # File path must be sanitized to basename only
    source_info = inv_data.get("source", {})
    file_path = source_info.get("file_path", "")
    assert "\\" not in file_path
    assert "/" not in file_path

    # Also inspect return payload inventory
    ret_inv = result["inventory"]
    ret_file_path = ret_inv.get("source", {}).get("file_path", "")
    assert "\\" not in ret_file_path
    assert "/" not in ret_file_path


def test_geometry_package_restore_roundtrip(box_model, tmp_path):
    """F06: Geometry package archive (.zip) can be safely restored and verified."""
    geom_json = tmp_path / "model_geometry.json"
    write_package(box_model, geom_json)

    geom_zip = tmp_path / "model_geometry.zip"
    archive_package(geom_json, geom_zip)
    assert geom_zip.is_file()

    # Restore to a new location
    restored_json = tmp_path / "restored" / "model_geometry.json"
    package = restore_package(geom_zip, restored_json)

    assert package is not None
    assert restored_json.is_file()
    assert (tmp_path / "restored" / "model_geometry.payloads").is_dir()

    # Verify extracted meshes match original box_model
    original_vertices = box_model.elements[0].mesh.vertices
    restored_vertices = package["elements"]["fixture:1"]["mesh"]["vertices"]
    assert restored_vertices == original_vertices


def test_geometry_package_restore_corrupted_payload_detection(box_model, tmp_path):
    """F06: restore_package must detect corrupted binary payload in archive and raise ValueError."""
    geom_json = tmp_path / "model_geometry.json"
    write_package(box_model, geom_json)

    geom_zip = tmp_path / "model_geometry.zip"
    archive_package(geom_json, geom_zip)

    # Tamper 1 byte inside a payload in the zip
    corrupt_zip = tmp_path / "corrupted_geometry.zip"
    with zipfile.ZipFile(geom_zip, "r") as src, zipfile.ZipFile(corrupt_zip, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename.endswith(".bin"):
                data = data[:-1] + (b"\xff" if data[-1:] != b"\xff" else b"\xee")
            dst.writestr(item, data)

    # Restoring corrupted archive must fail with ValueError
    with pytest.raises(ValueError, match="Corrupted payload in archive"):
        restore_package(corrupt_zip, tmp_path / "bad_restored" / "model_geometry.json")


def test_geometry_package_restore_prevents_zip_slip(tmp_path):
    """F06: restore_package must reject archives containing malicious path traversal entries."""
    evil_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil_zip, "w") as archive:
        archive.writestr("../../evil.bin", b"malicious content")
        archive.writestr("index.json", b"{}")

    with pytest.raises(ValueError, match="Security: Malicious path traversal"):
        restore_package(evil_zip, tmp_path / "safe" / "index.json")


def test_cli_profile_choices_geometry_fidelity():
    """F07: CLI convert and audit must accept --profile geometry-fidelity."""
    # Test convert subcommand with --help
    with pytest.raises(SystemExit) as exc:
        cli_main(["convert", "--help"])
    assert exc.value.code == 0

    # Test audit subcommand with --help
    with pytest.raises(SystemExit) as exc:
        cli_main(["audit", "--help"])
    assert exc.value.code == 0
