import numpy as np
import pytest
from ifc_to_fds.core.federation import load_sources
from ifc_to_fds.pipeline import convert, audit
from ifc_to_fds.mapping.manifest import MappingManifest


def test_federation_same_guid_different_sources(tiny_ifc, tmp_path):
    path, file, wall = tiny_ifc
    wall.Name = "Second source wall"
    second = tmp_path / "second.ifc"
    file.write(str(second))
    transform = np.eye(4)
    transform[0, 3] = 10.0
    model = load_sources(
        [path, second],
        {"transforms": {"0": np.eye(4).tolist(), "1": transform.tolist()}},
    )
    matches = [e for e in model.elements if e.global_id == wall.GlobalId]
    assert len(matches) == 2
    assert len({e.entity_key for e in matches}) == 2
    assert matches[1].bounding_box.xmin - matches[0].bounding_box.xmin == pytest.approx(
        10.0
    )
    with pytest.raises(ValueError, match="Ambiguous"):
        model.get_element_by_guid(wall.GlobalId)


def test_federation_requires_coordinates_and_rejects_duplicate(tiny_ifc, tmp_path):
    path, file, wall = tiny_ifc
    with pytest.raises(ValueError, match="coordinate"):
        load_sources([path, path])
    with pytest.raises(ValueError, match="Duplicate"):
        load_sources([path, path], {"common_coordinates": True})
    wall.Name = "different"
    second = tmp_path / "other.ifc"
    file.write(str(second))
    bad = np.eye(4)
    bad[0, 0] = 2
    with pytest.raises(ValueError, match="rigid"):
        load_sources(
            [path, second],
            {"common_coordinates": True, "transforms": {"1": bad.tolist()}},
        )


def test_saved_audit_detects_manifest_and_source_tampering(tiny_ifc):
    path, file, wall = tiny_ifc
    result = convert([path])
    manifest = MappingManifest.model_validate(result["manifest"])
    _, final, report = audit([path], result["fds_text"], manifest)
    assert report.gates["source_inventory"].status == "PASS"
    assert report.gates["geometry"].status == "PASS"
    assert final.acceptance_status == report.status
    next(
        r for r in manifest.records if r.ifc_type == "IfcWall"
    ).mapping_strategy = "SEMANTIC_ONLY"
    _, _, report = audit([path], result["fds_text"], manifest)
    assert report.status == "REJECTED" and report.gates["traceability"].status == "FAIL"
    wall.Name = "tampered source"
    file.write(str(path))
    _, _, report = audit([path], result["fds_text"], manifest)
    assert report.gates["source_inventory"].status == "FAIL"


def test_graph_mutation_rejected(tiny_ifc):
    path, _, _ = tiny_ifc
    result = convert([path])
    manifest = MappingManifest.model_validate(result["manifest"])
    manifest.configuration["mep_graph"]["connections"].append({"invented": "edge"})
    _, _, report = audit([path], result["fds_text"], manifest)
    assert report.gates["mep"].status == "FAIL"
