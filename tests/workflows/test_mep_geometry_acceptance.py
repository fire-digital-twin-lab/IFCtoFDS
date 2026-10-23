"""Check actual MEP solids, semantics, provenance and deliberately damaged output."""

import copy
import hashlib
import json
import re

import numpy as np
import pytest

from ifc_to_fds.modules.fds.api import MappingManifest, parse_fds
from ifc_to_fds.modules.geometry.api import as_trimesh, valid_solid
from ifc_to_fds.pipeline import audit, convert
from tests.support.mep_geometry import create_mep_geometry_ifc


@pytest.fixture
def mep_conversion(tmp_path):
    source = tmp_path / "authored-mep-fire.ifc"
    expected = create_mep_geometry_ifc(source)
    configuration = {"profile": "geometry-fidelity"}
    result = convert([source], configuration, output_directory=tmp_path / "conversion")
    return source, expected, configuration, result


def test_mep_geometry_and_explicit_network_are_verified(mep_conversion):
    source, expected, _, result = mep_conversion
    report = result["report"]
    assert result["mapping_status"] == "MAPPING_VERIFIED", report["findings"]
    assert report["matched_count"] == 8
    assert report["missing_count"] == report["deviated_count"] == 0
    for gate in [
        "geometry",
        "geometry_preservation",
        "mep",
        "placement",
        "traceability",
    ]:
        assert report["gates"][gate]["status"] == "PASS"
    assert (
        result["manifest"]["source_sha256"]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    records = {r["global_id"]: r for r in result["manifest"]["records"]}
    assert set(expected["members"]) <= records.keys()
    for guid, specification in expected["members"].items():
        record = records[guid]
        assert record["ifc_type"] == specification["ifc_type"]
        assert {p["port_global_id"] for p in record["ports"]} == set(
            specification["ports"]
        )
        assert record["fds_primitive_ids"]
        assert record["operational_status"] == "NOT_CONFIGURED"
        assert record["geometry_preservation"] == "PRESERVED"
    relationships = report["coverage"]["mep"]["source_relationships"]
    assert relationships["distribution_ports"] == 14
    assert (
        relationships["explicit_port_relations"]
        == relationships["accounted_edge_relations"]
        == 6
    )
    assert (
        relationships["unresolved_system_keys"]
        == relationships["orphan_port_keys"]
        == []
    )
    for category in ["VENTILATION", "FIRE_SUPPRESSION"]:
        coverage = report["coverage"]["mep_systems"][category]
        assert (
            coverage["source_count"]
            == coverage["geometry_verified"]
            == coverage["fds_obstacles"]
            == 4
        )
        assert coverage["operational_configured"] == 0
    assert report["simulation_status"] == "INCONCLUSIVE"


def test_duct_solids_preserve_the_analytic_hollow_section(mep_conversion):
    _, expected, _, result = mep_conversion
    from ifc_to_fds.domain.bim import TriangleMesh

    entries = {
        e["global_id"]: e for e in result["geometry_package"]["elements"].values()
    }
    for guid, specification in expected["members"].items():
        mesh = TriangleMesh.model_validate(entries[guid]["mesh"])
        assert valid_solid(mesh)
        tm = as_trimesh(mesh)
        analytic = specification["analytic_volume_m3"]
        if analytic is not None:
            assert tm.volume == pytest.approx(analytic, rel=1e-10, abs=1e-12)
            midpoint = np.mean(
                [specification["axis_start"], specification["axis_end"]], axis=0
            )
            # A filled bbox would erase the duct passage and fail both assertions.
            assert not tm.contains([midpoint])[0]


def test_rehashed_translated_fire_pipe_is_rejected(mep_conversion):
    source, _, configuration, result = mep_conversion
    manifest = MappingManifest.model_validate(result["manifest"])
    pipe = next(r for r in manifest.records if r.ifc_type == "IfcPipeSegment")
    pid = pipe.fds_primitive_ids[0]
    pattern = re.compile(
        r"(&GEOM\s+ID='" + re.escape(pid) + r"'.*?VERTS=)(.*?)(,\s*FACES=)", re.S
    )

    def translate(match):
        coordinates = [
            float(x) for x in match[2].replace("\n", "").split(",") if x.strip()
        ]
        coordinates[0::3] = [x + 0.25 for x in coordinates[0::3]]
        return match[1] + ",".join(format(x, ".17g") for x in coordinates) + match[3]

    text, count = pattern.subn(translate, result["fds_text"])
    assert count == 1 and not parse_fds(text).errors
    manifest.fds_sha256 = hashlib.sha256(text.encode()).hexdigest()
    _, _, report = audit(
        [source], text, manifest, configuration, result["geometry_package"]
    )
    assert report.mapping_status == "REJECTED"
    assert report.gates["geometry"].status == "FAIL"
    assert any(
        f.element_id == pipe.entity_key and f.category == "geometry"
        for f in report.findings
    )


def test_deleted_explicit_connection_is_rejected(mep_conversion):
    source, _, configuration, result = mep_conversion
    altered = copy.deepcopy(configuration)
    altered["mep_graph"] = copy.deepcopy(result["mep_graph"])
    altered["mep_graph"]["connections"].pop()
    manifest = MappingManifest.model_validate(result["manifest"])
    _, _, report = audit(
        [source], result["fds_text"], manifest, altered, result["geometry_package"]
    )
    assert report.mapping_status == "REJECTED"
    assert report.gates["mep"].status == "FAIL"


@pytest.mark.parametrize("corrupt", [False, True])
def test_handoff_reopens_source_and_never_infers_pyrosim_success(
    mep_conversion, tmp_path, monkeypatch, corrupt
):
    from ifc_to_fds.pipeline import save_artifacts
    from scripts.prepare_pyrosim_acceptance import main
    import shutil

    source, _, _, result = mep_conversion
    fds = tmp_path / "model.fds"
    save_artifacts(result, fds)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if corrupt:
        text = fds.read_bytes().decode().replace("VERTS=", "VERTS=999,999,999,", 1)
        fds.write_bytes(text.encode())
    original = fds.read_bytes()
    monkeypatch.setattr(shutil, "which", lambda _: None)
    output = tmp_path / "handoff"
    status = main(
        [
            str(fds),
            "--output",
            str(output),
            "--ifc",
            str(source),
            "--manifest",
            str(tmp_path / "model_manifest.json"),
            "--geometry-package",
            str(tmp_path / "model_geometry.json"),
            "--require-ready",
            "--roundtrip",
            str(fds),
        ]
    )
    report = json.loads((output / "acceptance.json").read_text(encoding="utf-8"))
    assert report["mapping"]["status"] == ("FAIL" if corrupt else "PASS")
    assert report["handoff"]["status"] == ("FAIL" if corrupt else "BLOCKED")
    assert status == (1 if corrupt else 2)
    assert report["pyrosim_import"]["status"] == "BLOCKED"
    assert fds.read_bytes() == original
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
