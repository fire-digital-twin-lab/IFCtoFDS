import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ifc_to_fds.domain.bim import (
    CanonicalElement,
    CanonicalModel,
    StoreyReference,
)
from ifc_to_fds.domain.source import SourceMetadata

SCRIPT_PATH = ROOT / "scripts" / "run-feature1-test.py"
SPEC = importlib.util.spec_from_file_location("feature1_acceptance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
feature1_acceptance = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = feature1_acceptance
SPEC.loader.exec_module(feature1_acceptance)


def model_with_storeys():
    source = SourceMetadata(
        source_id="source-hash",
        filename="building.ifc",
        file_path="building.ifc",
        file_hash_sha256="source-hash",
        file_size_bytes=1,
        schema_version="IFC4",
    )
    storeys = [
        StoreyReference(
            storey_id="source-hash:1",
            source_id="source-hash",
            building_id="source-hash:building-1",
            name="B1",
        ),
        StoreyReference(
            storey_id="source-hash:2",
            source_id="source-hash",
            building_id="source-hash:building-1",
            name="B2",
        ),
        StoreyReference(
            storey_id="source-hash:3",
            source_id="source-hash",
            building_id="source-hash:building-2",
            name="B10",
        ),
        StoreyReference(
            storey_id="source-hash:4",
            source_id="source-hash",
            building_id="source-hash:building-2",
            name="Lobby B2 West",
        ),
        StoreyReference(
            storey_id="source-hash:duplicate",
            source_id="source-hash",
            building_id="source-hash:building-1",
            name="B1",
        ),
    ]
    elements = [
        CanonicalElement(
            source_id="source-hash",
            entity_key=f"source-hash:{step_id}",
            global_id=f"guid-{step_id}",
            step_id=step_id,
            ifc_type="IfcWall",
            storey_id=f"source-hash:{step_id}",
            storey=storey.name,
        )
        for step_id, storey in enumerate(storeys, start=1)
    ]
    return CanonicalModel(
        source=source,
        sources=[source],
        elements=elements,
        storey_references=storeys,
    )


def test_feature1_requires_exact_source_qualified_b1_b2_ids():
    model = model_with_storeys()

    assert feature1_acceptance.validate_storey_ids(
        model, ["source-hash:1", "source-hash:2"], ["B1", "B2"]
    ) == ["source-hash:1", "source-hash:2"]
    with pytest.raises(ValueError, match="same identified building"):
        feature1_acceptance.validate_storey_ids(
            model, ["source-hash:3", "source-hash:1"], ["B1", "B2"]
        )
    with pytest.raises(ValueError, match="same identified building"):
        feature1_acceptance.validate_storey_ids(
            model, ["source-hash:1", "source-hash:4"], ["B1", "B2"]
        )
    with pytest.raises(ValueError, match="labels"):
        feature1_acceptance.validate_storey_ids(
            model, ["source-hash:1", "source-hash:2"], ["B1", "B1"]
        )
    with pytest.raises(ValueError, match="exactly one B1 and one B2"):
        feature1_acceptance.validate_storey_ids(
            model, ["source-hash:1", "source-hash:duplicate"], ["B1", "B2"]
        )

    with pytest.raises(ValueError, match="Exactly two"):
        feature1_acceptance.validate_storey_ids(model, [], [])
    with pytest.raises(ValueError, match="Exactly two"):
        feature1_acceptance.validate_storey_ids(model, ["B1"], ["B1"])
    with pytest.raises(ValueError, match="Unknown or non-source-qualified"):
        feature1_acceptance.validate_storey_ids(model, ["B1", "B2"], ["B1", "B2"])
    with pytest.raises(ValueError, match="Duplicate"):
        feature1_acceptance.validate_storey_ids(
            model, ["source-hash:1", "source-hash:1"], ["B1", "B2"]
        )
    with pytest.raises(ValueError, match="Unknown or non-source-qualified"):
        feature1_acceptance.validate_storey_ids(
            model, ["source-hash:1", "source-hash:missing"], ["B1", "B2"]
        )


def test_feature1_rejects_storeys_from_another_source():
    model = model_with_storeys()
    model.storey_references.append(
        StoreyReference(storey_id="other-hash:2", source_id="other-hash", name="B2")
    )
    with pytest.raises(ValueError, match="verified source IFC"):
        feature1_acceptance.validate_storey_ids(
            model, ["source-hash:1", "other-hash:2"], ["B1", "B2"]
        )


def test_feature1_requires_valid_separate_domain_and_evidence(tmp_path):
    domain_file = tmp_path / "domain.json"
    evidence_file = tmp_path / "domain-review.md"
    domain = {
        "xmin": 0,
        "xmax": 10,
        "ymin": 0,
        "ymax": 8,
        "zmin": -8,
        "zmax": 0,
    }
    domain_file.write_text(json.dumps(domain), encoding="utf-8")
    evidence_file.write_text("Reviewed boundary evidence", encoding="utf-8")

    domain_values, evidence = feature1_acceptance.load_simulation_domain(
        domain_file,
        evidence_file,
        {key: float(value) for key, value in domain.items()},
    )
    assert domain_values == {key: float(value) for key, value in domain.items()}
    assert evidence["file"] == str(evidence_file)
    assert len(evidence["sha256"]) == 64

    with pytest.raises(ValueError, match="evidence file does not exist"):
        feature1_acceptance.load_simulation_domain(
            domain_file, tmp_path / "missing.md", None
        )

    domain_file.write_text(json.dumps({"xmin": 0, "xmax": 0}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid simulation domain"):
        feature1_acceptance.load_simulation_domain(
            domain_file,
            evidence_file,
            {key: float(value) for key, value in domain.items()},
        )


def test_feature1_b1_b2_scope_is_not_inferred_from_storey_labels():
    model = model_with_storeys()
    selected_ids = feature1_acceptance.validate_storey_ids(
        model, ["source-hash:1", "source-hash:2"], ["B1", "B2"]
    )
    elements = [element for element in model.elements if element.storey_id in selected_ids]

    assert [element.storey for element in elements] == ["B1", "B2"]
    assert all(element.storey != "B10" for element in elements)
    assert all(element.storey != "Lobby B2 West" for element in elements)


def test_feature1_reference_requires_matching_source_hash_and_approval(monkeypatch):
    bundle = {
        "sources.json": {"sources": [{"file_hash_sha256": "a" * 64}]},
        "scope.json": {
            "scope": {"storeys": ["source-hash:1", "source-hash:2"]},
            "simulation_domain": {
                "xmin": 0,
                "xmax": 10,
                "ymin": 0,
                "ymax": 8,
                "zmin": -8,
                "zmax": 0,
            }
        },
    }
    approval = {
        "status": "DRAFT",
        "reviewer": None,
        "rationale": None,
        "evidence": [],
        "bundle_sha256": "bundle-digest",
    }

    def inspect_reference(case: Path) -> tuple[str, dict, dict]:
        assert case == Path("reference")
        return "bundle-digest", approval, bundle

    monkeypatch.setattr(feature1_acceptance, "inspect_case", inspect_reference)

    with pytest.raises(ValueError, match="does not match"):
        feature1_acceptance.verify_reference_case(Path("reference"), "b" * 64)
    draft_result = feature1_acceptance.verify_reference_case(Path("reference"), "a" * 64)
    assert draft_result["status"] == "DRAFT"
    assert draft_result["simulation_domain"]["xmax"] == 10.0
    assert draft_result["scope_storey_ids"] == []
    assert draft_result["reference_scope_status"] == "UNAPPROVED_DRAFT"
    assert draft_result["approved_reference"] is False

    approval.update(
        status="APPROVED",
        reviewer="reviewer",
        rationale="Reviewed source and boundary evidence",
        evidence=["evidence.md"],
    )
    verified = feature1_acceptance.verify_reference_case(Path("reference"), "a" * 64)
    assert verified["status"] == "APPROVED"
    assert verified["simulation_domain"]["xmax"] == 10.0
    assert verified["approved_reference"] is True
    bundle["scope.json"]["scope"]["storeys"] = []
    with pytest.raises(ValueError, match="exactly two source-qualified storey IDs"):
        feature1_acceptance.verify_reference_case(Path("reference"), "a" * 64)
    bundle["scope.json"]["scope"]["storeys"] = ["source-hash:1", "source-hash:2"]

    bundle["scope.json"]["scope"] = {}
    with pytest.raises(ValueError, match="exactly two source-qualified storey IDs"):
        feature1_acceptance.verify_reference_case(Path("reference"), "a" * 64)
    bundle["scope.json"]["scope"] = {"storeys": ["source-hash:1", "source-hash:2"]}

    bundle["scope.json"]["simulation_domain"] = None
    with pytest.raises(ValueError, match="no independently reviewed simulation domain"):
        feature1_acceptance.verify_reference_case(Path("reference"), "a" * 64)

    bundle["scope.json"]["simulation_domain"] = {
        "xmin": 0,
        "xmax": 10,
        "ymin": 0,
        "ymax": 8,
        "zmin": -8,
        "zmax": 0,
    }
    bundle["scope.json"]["scope"]["storeys"] = ["source-hash:1"]
    with pytest.raises(ValueError, match="differ from the reference case scope"):
        feature1_acceptance.validate_storey_ids(
            model_with_storeys(),
            ["source-hash:1", "source-hash:2"],
            ["B1", "B2"],
            ["source-hash:1"],
        )
