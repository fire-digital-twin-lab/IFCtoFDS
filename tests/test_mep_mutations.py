from copy import deepcopy
from pathlib import Path
import pytest

from ifc_to_fds.pipeline import convert, audit
from ifc_to_fds.mapping.manifest import MappingManifest


@pytest.mark.parametrize("mutation", ["edge", "owner", "system"])
def test_saved_network_mutation_identifies_affected_entities(tmp_path, mutation):
    source = Path(__file__).parent / "baseline/fixtures/mep.ifc"
    result = convert([str(source)], output_directory=tmp_path)
    config = deepcopy(result["configuration"])
    graph = config["mep_graph"]
    edge = graph["connections"][0]
    affected = edge["source_element_id"]
    if mutation == "edge":
        graph["connections"].pop(0)
    elif mutation == "owner":
        edge["source_element_id"] = edge["target_element_id"]
    else:
        system = graph["systems"][0]
        affected = system["element_keys"][0]
        system["element_keys"].pop(0)
    _, _, report = audit(
        [str(source)],
        result["fds_text"],
        MappingManifest.model_validate(result["manifest"]),
        config,
        result["geometry_package"],
    )
    assert report.gates["mep"].status == "FAIL"
    assert any(
        f.category == "mep" and f.element_id == affected for f in report.findings
    )


def test_manifest_source_label_mutation_is_not_accepted(box_model):
    from ifc_to_fds.mapping.exporter import serialize_fds
    from ifc_to_fds.validation.engine import run_independent_validation

    text, manifest = serialize_fds(box_model)
    manifest.records[0].ifc_type = "IfcDoor"
    report = run_independent_validation(box_model, text, manifest)
    assert report.gates["traceability"].status == "FAIL"
    assert any(
        f.category == "traceability" and f.element_id == "fixture:1"
        for f in report.findings
    )
