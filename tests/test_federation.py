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


def test_rebase_vector_shape_validated():
    from ifc_to_fds.application.dto.configuration import validate_configuration

    with pytest.raises(ValueError):
        validate_configuration({"rebase_vector": [1, 2]})
    with pytest.raises(ValueError):
        validate_configuration({"rebase_vector": ["a", 0, 0]})
    with pytest.raises(ValueError):
        validate_configuration({"rebase_vector": [float("nan"), 0, 0]})
    with pytest.raises(ValueError):
        validate_configuration({"rebase_vector": [float("inf"), 0, 0]})
    config = validate_configuration({"rebase_vector": [1, 2, 3]})
    assert list(config["rebase_vector"]) == [1, 2, 3]


def test_graph_mutation_rejected(tiny_ifc):
    path, _, _ = tiny_ifc
    result = convert([path])
    manifest = MappingManifest.model_validate(result["manifest"])
    manifest.configuration["mep_graph"]["connections"].append({"invented": "edge"})
    _, _, report = audit([path], result["fds_text"], manifest)
    assert report.gates["mep"].status == "FAIL"


def test_federation_transforms_representation_bounds_and_empty_mesh(tiny_ifc, tmp_path):
    from ifc_to_fds.domain.bim import BoundingBox, TriangleMesh

    path, file, wall = tiny_ifc
    wall.Name = "Second wall"
    second = tmp_path / "second_rb.ifc"
    file.write(str(second))

    transform = np.eye(4)
    transform[0, 3] = 5.0
    transform[1, 3] = 10.0
    transform[2, 3] = 2.0

    model = load_sources(
        [path, second],
        {"transforms": {"0": np.eye(4).tolist(), "1": transform.tolist()}},
    )
    matches = [e for e in model.elements if e.global_id == wall.GlobalId]
    assert len(matches) == 2
    elem1 = matches[1]

    rb = BoundingBox(xmin=0, xmax=2, ymin=0, ymax=1, zmin=0, zmax=3)
    elem1.representation_bounds = rb
    elem1.mesh = TriangleMesh(vertices=[], faces=[])

    from ifc_to_fds.core.federation import bounds_for_vertices
    corners = [
        [x, y, z]
        for x in (rb.xmin, rb.xmax)
        for y in (rb.ymin, rb.ymax)
        for z in (rb.zmin, rb.zmax)
    ]
    transformed_corners = (np.asarray(corners) @ transform[:3, :3].T + transform[:3, 3]).tolist()
    elem1.representation_bounds = bounds_for_vertices(transformed_corners)

    assert elem1.representation_bounds is not None
    assert elem1.representation_bounds.xmin == pytest.approx(5.0)
    assert elem1.representation_bounds.xmax == pytest.approx(7.0)
    assert elem1.representation_bounds.ymin == pytest.approx(10.0)
    assert elem1.representation_bounds.ymax == pytest.approx(11.0)
    assert elem1.representation_bounds.zmin == pytest.approx(2.0)
    assert elem1.representation_bounds.zmax == pytest.approx(5.0)


def test_rebase_vector_rejects_bool():
    """P2/C5: bool is an int subclass -- [True, 0, 0] must be rejected."""
    from ifc_to_fds.application.dto.configuration import validate_configuration

    with pytest.raises(ValueError):
        validate_configuration({"rebase_vector": [True, 0, 0]})


def test_load_sources_rebase_vector_shape_raises_value_error(tiny_ifc):
    """federation.py must raise ValueError (not bare assert) on bad rebase shape."""
    path, _, _ = tiny_ifc
    with pytest.raises(ValueError, match="rebase_vector must be"):
        load_sources([path], {"rebase_vector": [1, 2]})

