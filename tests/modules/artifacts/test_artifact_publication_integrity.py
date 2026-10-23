"""Publication, reader integrity and checkpoint failure regressions."""

import json
from pathlib import Path

import pytest

from ifc_to_fds.modules.artifacts.api import LocalConversionWorkspaces, LocalFilesystemArtifactRepository
from ifc_to_fds.modules.artifacts.contracts import CheckpointPayload
from ifc_to_fds.modules.fds.api import MappingManifest
from ifc_to_fds.modules.geometry.api import payload_dir, seal
from ifc_to_fds.pipeline import convert, save_artifacts


@pytest.fixture
def run(tiny_ifc, tmp_path):
    return convert([tiny_ifc[0]], output_directory=tmp_path / "work")


def snapshot(directory):
    return {str(p.relative_to(directory)): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()}


def inline_result(run):
    package = run["geometry_package"]
    inline = {k: v for k, v in package.index.items() if k != "storage_format"}
    inline["elements"] = dict(package["elements"].items())
    inline = seal(inline)
    manifest = MappingManifest.model_validate(run["manifest"])
    manifest.geometry_package_sha256 = inline["sha256"]
    manifest.reseal()
    return {**run, "geometry_package": inline, "manifest": manifest.model_dump(mode="json")}


@pytest.mark.parametrize("mutation", ["payload_bytes", "index_bytes", "inline_checksum"])
def test_corrupt_geometry_is_rejected_before_replacing_an_existing_bundle(run, tmp_path, mutation):
    target = tmp_path / "published/model.fds"
    save_artifacts(run, target)
    before = snapshot(target.parent)
    package = run["geometry_package"]
    if mutation == "payload_bytes":
        payload = next(payload_dir(package.path).glob("*.bin"))
        data = bytearray(payload.read_bytes())
        data[-1] ^= 1
        payload.write_bytes(data)
    elif mutation == "index_bytes":
        index = json.loads(package.path.read_text())
        index["units"] = "MILLIMETRE"
        package.path.write_text(json.dumps(index), encoding="utf-8")
    else:
        run = inline_result(run)
        next(iter(run["geometry_package"]["elements"].values()))["mesh"]["vertices"][0][0] += 1
    with pytest.raises(ValueError):
        save_artifacts(run, target)
    assert snapshot(target.parent) == before


def test_inline_republication_removes_unreferenced_binary_payloads(run, tmp_path):
    target = tmp_path / "published/model.fds"
    save_artifacts(run, target)
    assert payload_dir(target.with_name("model_geometry.json")).is_dir()
    save_artifacts(inline_result(run), target)
    assert not payload_dir(target.with_name("model_geometry.json")).exists()


def test_old_unreferenced_payloads_are_not_published_or_deleted_from_source(run, tmp_path):
    source = payload_dir(run["geometry_package"].path)
    orphan = source / ("0" * 64 + ".bin")
    orphan.write_bytes(b"Unreferenced geometry from a previous run")
    target = tmp_path / "published/model.fds"
    save_artifacts(run, target)
    assert orphan.read_bytes() == b"Unreferenced geometry from a previous run"
    assert not (payload_dir(target.with_name("model_geometry.json")) / orphan.name).exists()


def test_inline_publication_failure_restores_the_previous_payloads(run, tmp_path, monkeypatch):
    target = tmp_path / "published/model.fds"
    save_artifacts(run, target)
    before = snapshot(target.parent)
    original = Path.replace

    def fail_manifest(path, destination):
        if path.parent.name.startswith(".staging-") and path.name.endswith("_manifest.json"):
            raise OSError("publication failure")
        return original(path, destination)

    monkeypatch.setattr(Path, "replace", fail_manifest)
    with pytest.raises(OSError, match="publication failure"):
        save_artifacts(inline_result(run), target)
    assert snapshot(target.parent) == before


@pytest.mark.parametrize("same_target", [True, False])
def test_publication_lock_prevents_interleaved_writers(run, tmp_path, monkeypatch, same_target):
    from ifc_to_fds.modules.artifacts.infrastructure import filesystem_repository as storage

    target = tmp_path / "published/model.fds"
    other = target if same_target else target.with_name("other.fds")
    original = storage.copy_package
    triggered = False

    def concurrent_writer(*args, **kwargs):
        nonlocal triggered
        if not triggered:
            triggered = True
            if same_target:
                with pytest.raises(FileExistsError, match="in progress"):
                    LocalFilesystemArtifactRepository().save_run_artifacts(run, other)
            else:
                LocalFilesystemArtifactRepository().save_run_artifacts(run, other)
        return original(*args, **kwargs)

    monkeypatch.setattr(storage, "copy_package", concurrent_writer)
    save_artifacts(run, target)
    assert triggered
    assert not list(target.parent.glob(".publish-*.lock"))
    if not same_target:
        assert other.is_file()


@pytest.mark.parametrize("suffix", [".ifc", ".json", ""])
def test_output_extension_cannot_collide_with_source_or_evidence(run, tmp_path, suffix):
    target = tmp_path / ("model" + suffix)
    target.write_bytes(b"Existing source or evidence")
    with pytest.raises(ValueError, match=".fds"):
        save_artifacts(run, target)
    assert target.read_bytes() == b"Existing source or evidence"


@pytest.mark.parametrize("mutation", [None, "fds", "report", "archive", "payload", "checksum_inventory"])
def test_reopen_published_bundle_checks_all_declared_files_and_geometry(run, tmp_path, mutation):
    from ifc_to_fds.modules.artifacts.api import verify_run_artifacts

    target = tmp_path / "published/model.fds"
    save_artifacts(run, target)
    if mutation == "checksum_inventory":
        path = target.with_name("model_checksums.json")
        entries = json.loads(path.read_text())
        entries["../outside.txt"] = "0" * 64
        path.write_text(json.dumps(entries), encoding="utf-8")
    elif mutation:
        paths = {"fds": target, "report": target.with_name("model_acceptance_report.json"),
                 "archive": target.with_name("model_geometry.zip")}
        path = next(payload_dir(target.with_name("model_geometry.json")).glob("*.bin")) if mutation == "payload" else paths[mutation]
        path.write_bytes(path.read_bytes() + b"corrupted")
    if mutation:
        with pytest.raises(ValueError):
            verify_run_artifacts(target)
    else:
        checked = verify_run_artifacts(target)
        assert checked["status"] == "PASS"
        assert checked["scope"] == "ARTIFACT_BYTES_AND_GEOMETRY_PAYLOAD_INTEGRITY"
        assert len(checked["files"]) == 12


@pytest.mark.parametrize("failure", ["geometry", "checkpoint"])
def test_reused_workspace_is_unsealed_before_any_new_write(run, tmp_path, box_model, monkeypatch, failure):
    from ifc_to_fds.modules.artifacts.infrastructure import conversion_workspace as storage

    directory = tmp_path / "work"
    assert json.loads((directory / "audit-state.json").read_text())["checkpoint_status"] == "VERIFIED_SEALED"
    workspace = LocalConversionWorkspaces().open(directory)
    with pytest.raises((OSError, TypeError)):
        if failure == "geometry":
            def fail(*args, **kwargs):
                raise OSError("geometry write failure")
            monkeypatch.setattr(storage, "write_package", fail)
            workspace.write_geometry(box_model, "new geometry")
        else:
            manifest = MappingManifest.model_validate(run["manifest"])
            payload = CheckpointPayload(inventory={"invalid": object()}, mep_graph={}, configuration={})
            workspace.checkpoint(payload, manifest)
    state = json.loads((directory / "audit-state.json").read_text())
    assert state["checkpoint_status"] == "DRAFT_NOT_SEALED"
    assert state["output_complete"] is False


def test_state_publication_failure_keeps_the_previous_valid_json(run, tmp_path, monkeypatch):
    from ifc_to_fds.modules.verification.contracts import AcceptanceReport

    workspace = LocalConversionWorkspaces().open(tmp_path / "work")
    path = tmp_path / "work/audit-state.json"
    before = path.read_bytes()
    original = Path.replace

    def fail_state(source, destination):
        if Path(destination) == path:
            raise OSError("state publication failure")
        return original(source, destination)

    monkeypatch.setattr(Path, "replace", fail_state)
    with pytest.raises(OSError, match="state publication failure"):
        workspace.complete(MappingManifest.model_validate(run["manifest"]),
                           AcceptanceReport.model_validate(run["report"]), {})
    assert path.read_bytes() == before
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize("mutation", ["incomplete", "stale_manifest_hash"])
def test_workspace_does_not_seal_incomplete_or_unsealed_manifest(run, tmp_path, mutation):
    from ifc_to_fds.modules.verification.contracts import AcceptanceReport

    workspace = LocalConversionWorkspaces().open(tmp_path / "work")
    manifest = MappingManifest.model_validate(run["manifest"])
    if mutation == "incomplete":
        manifest.output_complete = False
    else:
        manifest.records[0].name = "Changed after sealing"
    workspace.complete(manifest, AcceptanceReport.model_validate(run["report"]), {})
    state = json.loads((tmp_path / "work/audit-state.json").read_text())
    assert state["checkpoint_status"] == "DRAFT_NOT_SEALED"
    assert state["status"] == "INCONCLUSIVE"
    assert state["output_complete"] is False
