"""R10-03: checkpoint artifact compatibility and fail-closed audit boundaries."""

import ast
import json
from pathlib import Path

import pytest

from ifc_to_fds.adapters.storage.conversion_workspace import (
    LocalConversionWorkspace,
    LocalConversionWorkspaceFactory,
)
from ifc_to_fds.application.ports.conversion_workspace import (
    ConversionWorkspaceFactoryPort,
    ConversionWorkspacePort,
)
from ifc_to_fds.application.services.portable_inventory import (
    compact_inventory,
    sanitize_portable_paths,
)
from ifc_to_fds.bootstrap.container import create_container
from ifc_to_fds.domain.mapping import build_mapping_plan
from ifc_to_fds.mapping.exporter import serialize_fds


def test_factory_is_injected_and_matches_port_contract():
    use_case = create_container().get_convert_verified_use_case()
    assert isinstance(use_case.workspace_factory, ConversionWorkspaceFactoryPort)
    assert isinstance(use_case.workspace_factory.create(None), ConversionWorkspacePort)


def test_portable_inventory_strips_only_file_directories(box_model):
    data = {"file_path": "/tmp/project/model.ifc", "source": [
        {"file_path": "/tmp/assets/file.ifc", "geometry": [1, 2, 3]}
    ]}
    expected = {"file_path": "model.ifc", "source": [
        {"file_path": "file.ifc", "geometry": [1, 2, 3]}
    ]}
    assert sanitize_portable_paths(data) == expected
    assert data["file_path"].startswith("/tmp/")
    snapshot = compact_inventory(box_model)
    assert isinstance(snapshot, dict)
    assert "elements" in snapshot


def test_draft_persists_source_of_truth_before_audit(box_model, tmp_path):
    plan = build_mapping_plan(box_model, cell_size=0.5)
    fds_text, manifest = serialize_fds(box_model, cell_size=0.5, mapping_plan=plan)
    workspace = LocalConversionWorkspace(tmp_path)
    assert workspace.owner is None
    workspace.write_prepared(fds_text, plan)
    config = {
        "cell_size": 0.5,
        "mep_graph": box_model.mep_graph.model_dump(mode="json"),
    }
    manifest.configuration = config
    manifest.reseal()
    reloaded = workspace.write_draft(box_model, config, manifest)
    assert reloaded.model_dump(mode="json") == manifest.model_dump(mode="json")
    assert workspace.read_fds().encode("utf-8") == fds_text.encode("utf-8")
    assert (tmp_path / "mapping_plan.json").read_text(encoding="utf-8") == plan.model_dump_json()
    assert (tmp_path / "model_manifest.json").read_text(encoding="utf-8") == manifest.model_dump_json()
    checkpoint = json.loads((tmp_path / "audit-state.json").read_text(encoding="utf-8"))
    assert checkpoint == {
        "stage": "VALIDATION",
        "status": "NOT_RUN",
        "checkpoint_status": "DRAFT_NOT_SEALED",
        "output_complete": False,
        "bundle_sha256": manifest.bundle_sha256,
        "reason": "Artifacts saved; independent audit has not completed",
    }
    assert (tmp_path / "model_inventory.json").is_file()
    assert (tmp_path / "model_mep_graph.json").is_file()
    assert (tmp_path / "model_configuration.json").is_file()


@pytest.mark.parametrize("status,expected_seal", [
    ("MAPPING_VERIFIED", "VERIFIED_SEALED"),
    ("INCONCLUSIVE", "DRAFT_NOT_SEALED"),
    ("REJECTED", "DRAFT_NOT_SEALED"),
    ("NOT_RUN", "DRAFT_NOT_SEALED"),
])
def test_only_mapping_verified_status_is_sealed(tmp_path, status, expected_seal):
    class Manifest:
        bundle_sha256 = "fixture-digest"
        output_complete = False
        def model_dump_json(self):
            return '{"bundle_sha256":"fixture-digest"}'

    workspace = LocalConversionWorkspace(tmp_path)
    workspace.finish_audit(Manifest(), status, {"audit_s": 1.25})
    state = json.loads((tmp_path / "audit-state.json").read_text(encoding="utf-8"))
    assert state["status"] == status
    assert state["checkpoint_status"] == expected_seal
    assert state["bundle_sha256"] == "fixture-digest"
    assert state["timings"] == {"audit_s": 1.25}


def test_temporary_workspace_is_owned_by_factory():
    workspace = LocalConversionWorkspaceFactory().create(None)
    assert workspace.owner is not None
    assert workspace.directory.is_dir()
    assert workspace.geometry_path.parent == workspace.directory
    workspace.owner.cleanup()


def test_conversion_use_case_does_not_write_checkpoint_files_directly():
    from ifc_to_fds.application.use_cases import convert_verified
    tree = ast.parse(Path(convert_verified.__file__).read_text(encoding="utf-8"))
    methods = {"write_text", "write_bytes", "read_text", "read_bytes"}
    direct_io = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in methods
    ]
    assert direct_io == [], f"Conversion use case performs direct filesystem I/O: {direct_io}"
