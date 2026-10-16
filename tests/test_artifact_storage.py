import json
import pytest
from ifc_to_fds.geometry.storage import write_package, read_package, payload_dir
from ifc_to_fds.geometry.package import verify_package, audit_package, seal
from ifc_to_fds.validation.acceptance import AcceptanceReport, AuditConfig


def test_lossless_payload_and_corruption(box_model, tmp_path):
    path = tmp_path / "geometry.json"
    package = write_package(box_model, path)
    assert '"vertices":' not in path.read_text()
    assert (
        package["elements"]["fixture:1"]["mesh"]["vertices"]
        == box_model.elements[0].mesh.vertices
    )
    verify_package(package)
    payload = next(payload_dir(path).glob("*.bin"))
    payload.write_bytes(payload.read_bytes()[:-1])
    with pytest.raises(ValueError, match="corrupted"):
        verify_package(read_package(path))


def test_rehashed_changed_payload_is_not_geometry_evidence(box_model, tmp_path):
    from ifc_to_fds.geometry.storage import store_mesh

    path = tmp_path / "geometry.json"
    package = write_package(box_model, path)
    changed = box_model.elements[0].mesh.model_copy(deep=True)
    for vertex in changed.vertices:
        vertex[0] += 2
    index = package.index
    index["elements"]["fixture:1"]["mesh"] = store_mesh(changed, payload_dir(path))
    path.write_text(json.dumps(seal(index)))
    report = AcceptanceReport()
    audit_package(box_model, read_package(path), report, AuditConfig())
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(f.element_id == "fixture:1" for f in report.findings)


def test_public_result_does_not_include_mesh(tiny_ifc, tmp_path):
    from ifc_to_fds.pipeline import convert, save_artifacts
    from ifc_to_fds.results import public_result

    result = convert([tiny_ifc[0]], output_directory=tmp_path)
    save_artifacts(result, tmp_path / "model.fds")
    public = public_result(result)
    assert public["status"] == "MAPPING_VERIFIED", result["report"]["findings"]
    encoded = json.dumps(public)
    for name in (
        "geometry_package",
        "vertices",
        "faces",
        "fds_text",
        "element_statuses",
    ):
        assert name not in encoded
    assert len(public["findings"]) <= 20
    assert (tmp_path / "model_geometry.zip").is_file()
    import hashlib

    assert (
        hashlib.sha256((tmp_path / "model.fds").read_bytes()).hexdigest()
        == result["manifest"]["fds_sha256"]
    )


def test_public_size_independent_of_mesh_and_fds(tiny_ifc):
    from ifc_to_fds.pipeline import convert
    from ifc_to_fds.results import public_result

    result = convert([tiny_ifc[0]])
    before = json.dumps(public_result(result), sort_keys=True)
    result["geometry_package"] = {"vertices": [[1, 2, 3]] * 100000}
    result["fds_text"] = "x" * 1000000
    result["inventory"] = ["unused"] * 100000
    assert json.dumps(public_result(result), sort_keys=True) == before


def test_rehashed_index_role_mutation_fails(box_model, tmp_path):
    path = tmp_path / "geometry.json"
    package = write_package(box_model, path)
    index = package.index
    index["elements"]["fixture:1"]["simulation_role"] = "REFERENCE_GEOMETRY"
    path.write_text(json.dumps(seal(index)), encoding="utf-8")
    report = AcceptanceReport()
    audit_package(box_model, read_package(path), report, AuditConfig())
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(f.element_id == "fixture:1" for f in report.findings)
