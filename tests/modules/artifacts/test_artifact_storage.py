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


def test_original_v04_geometry_hash_is_preserved(box_model, tmp_path):
    from ifc_to_fds.geometry.package import build_package

    old = build_package(box_model)
    old["schema_version"] = "0.4.0"
    old = seal(old)
    path = tmp_path / "old.json"
    original = json.dumps(old).encode()
    path.write_bytes(original)
    loaded = read_package(path)
    verify_package(loaded)
    assert path.read_bytes() == original
    assert loaded["sha256"] == old["sha256"]


@pytest.mark.parametrize("mutation", ["missing", "corrupt"])
def test_bad_payload_reports_geometry_gate_and_entity(box_model, tmp_path, mutation):
    path = tmp_path / "geometry.json"
    write_package(box_model, path)
    payload = next(payload_dir(path).glob("*.bin"))
    if mutation == "missing":
        payload.unlink()
    else:
        payload.write_bytes(payload.read_bytes()[:-1])
    report = AcceptanceReport()
    audit_package(box_model, read_package(path), report, AuditConfig())
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(
        f.element_id == "fixture:1" and f.category == "geometry_preservation"
        for f in report.findings
    )


def test_manifest_to_csv_with_openings_and_ports(box_model, tmp_path):
    import csv
    from ifc_to_fds.core.canonical import OpeningReference, PortReference, BoundingBox
    from ifc_to_fds.mapping.manifest import build_manifest
    from ifc_to_fds.pipeline import save_artifacts

    elem = box_model.elements[0]
    elem.openings = [
        OpeningReference(
            opening_global_id="op-1",
            opening_step_id=101,
            opening_name="Window Void",
            bounding_box=BoundingBox(
                xmin=0.1, xmax=0.5, ymin=0.1, ymax=0.5, zmin=0.1, zmax=0.5
            ),
            is_subtracted=True,
        )
    ]
    elem.ports = [
        PortReference(
            port_global_id="port-1",
            port_step_id=201,
            name="Inlet",
            flow_direction="SOURCE",
            local_position=[0.0, 0.0, 0.0],
            world_position=[1.0, 2.0, 3.0],
            port_key="fixture:port-1",
        )
    ]
    elem.system_ids = ["SYS_VENT_1", "SYS_SMOKE_2"]
    manifest = build_manifest(box_model, fds_text="&OBST XB=0,1,0,1,0,1 /")

    # Verify to_csv executes without TypeError
    csv_text = manifest.to_csv()
    assert isinstance(csv_text, str)

    # Parse CSV and verify structured fields are valid JSON and string lists are semicolon-separated
    reader = csv.DictReader(csv_text.splitlines())
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]

    # Semicolon joined string lists
    assert row["system_ids"] == "SYS_VENT_1;SYS_SMOKE_2"

    # JSON serialized list of dicts for openings
    openings_data = json.loads(row["openings"])
    assert isinstance(openings_data, list) and len(openings_data) == 1
    assert openings_data[0]["opening_global_id"] == "op-1"
    assert openings_data[0]["opening_name"] == "Window Void"

    # JSON serialized list of dicts for ports
    ports_data = json.loads(row["ports"])
    assert isinstance(ports_data, list) and len(ports_data) == 1
    assert ports_data[0]["port_global_id"] == "port-1"
    assert ports_data[0]["name"] == "Inlet"

    # Verify save_artifacts writes _manifest.csv and all expected artifacts
    dummy_result = {
        "fds_text": "&HEAD TITLE='test' /\n&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n&OBST XB=0,2,0,1,0,3 /",
        "manifest": manifest.model_dump(mode="json"),
        "report": {"status": "INCONCLUSIVE", "gates": {}},
        "inventory": box_model.model_dump(
            mode="json", exclude={"elements": {"__all__": {"mesh": True}}}
        ),
        "mep_graph": box_model.mep_graph.model_dump(mode="json"),
        "configuration": {},
        "timings": {},
        "parity_report": {},
        "markdown_report": "# Test Report",
        "geometry_package": write_package(box_model, tmp_path / "pkg.json"),
    }
    out_file = tmp_path / "model.fds"
    save_artifacts(dummy_result, out_file)
    csv_file = tmp_path / "model_manifest.csv"
    assert csv_file.is_file()
    assert len(csv_file.read_text(encoding="utf-8")) > 0


def test_fzk_haus_e2e_conversion_and_artifacts(tmp_path):
    from pathlib import Path
    from ifc_to_fds.pipeline import convert, save_artifacts

    fzk_path = Path("examples/AC20-FZK-Haus.ifc")
    assert fzk_path.is_file()
    result = convert(
        [str(fzk_path)],
        configuration={"scope": {"storeys": ["Erdgeschoss"]}},
        output_directory=tmp_path,
    )
    output_fds = tmp_path / "fzk.fds"
    save_artifacts(result, output_fds)

    assert output_fds.is_file()
    assert (tmp_path / "fzk_manifest.json").is_file()
    csv_file = tmp_path / "fzk_manifest.csv"
    assert csv_file.is_file()
    assert csv_file.stat().st_size > 0
    assert (tmp_path / "fzk_acceptance_report.json").is_file()
    assert (tmp_path / "fzk_acceptance_report.md").is_file()
    assert (tmp_path / "fzk_geometry.json").is_file()
    assert (tmp_path / "fzk_geometry.zip").is_file()
    assert (tmp_path / "fzk_checksums.json").is_file()
    manifest_data = result["manifest"]
    assert isinstance(manifest_data, dict)
    # This real fixture has source topology/opening defects. It is a negative
    # acceptance case, even though publishing diagnostic files succeeds.
    assert len(manifest_data["records"]) == 127
    import json
    saved_report = json.loads((tmp_path / "fzk_acceptance_report.json").read_text(encoding="utf-8"))
    assert saved_report["mapping_status"] == result["mapping_status"] == "REJECTED"
    assert saved_report["gates"]["geometry"]["status"] == "FAIL"
    assert saved_report["gates"]["geometry_preservation"]["status"] == "FAIL"
    assert saved_report["gates"]["openings"]["status"] == "FAIL"
    assert saved_report["gates"]["source_inventory"]["status"] == "PASS"
    assert any(f["category"] == "geometry" and f["element_id"].endswith(":14502")
               for f in saved_report["findings"])


