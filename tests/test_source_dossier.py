"""Kiểm thử IFC dossier: đếm quan hệ, quyền riêng tư và fail-closed."""

import json
from pathlib import Path

import pytest

from ifc_to_fds.core.source_dossier import (
    assemble_source_dossier,
    inspect_source_dossier,
    write_source_dossier,
)


class Entity:
    def __init__(self, id_number, kind, **fields):
        self._id = id_number
        self._kind = kind
        for key, value in fields.items():
            setattr(self, key, value)

    def id(self):
        return self._id

    def is_a(self):
        return self._kind


class IFC:
    schema = "IFC2X3"

    def __init__(self, entities):
        self.entities = entities

    def by_type(self, name):
        return [entity for entity in self.entities if entity.is_a() == name]


def _fixture():
    h1 = Entity(1, "IfcBuildingStorey", Elevation=-4000.0, Name="Sensitive floor")
    h2 = Entity(2, "IfcBuildingStorey", Elevation=-7300.0)
    wall = Entity(3, "IfcWallStandardCase", Name="Sensitive wall")
    slab = Entity(4, "IfcSlab")
    opening1 = Entity(5, "IfcOpeningElement")
    opening2 = Entity(6, "IfcOpeningElement")
    door = Entity(7, "IfcDoor", GlobalId="PRIVATE-GUID")
    space = Entity(8, "IfcSpace", Name="PRIVATE_ROOM")
    entities = [h1, h2, wall, slab, opening1, opening2, door, space]
    entities.extend([
        Entity(9, "IfcRelContainedInSpatialStructure", RelatingStructure=h1, RelatedElements=(wall, door)),
        Entity(10, "IfcRelContainedInSpatialStructure", RelatingStructure=h2, RelatedElements=(slab,)),
        Entity(11, "IfcRelAggregates", RelatingObject=h1, RelatedObjects=(space,)),
        Entity(12, "IfcRelVoidsElement", RelatingBuildingElement=wall, RelatedOpeningElement=opening1),
        Entity(13, "IfcRelVoidsElement", RelatingBuildingElement=slab, RelatedOpeningElement=opening2),
        Entity(14, "IfcRelFillsElement", RelatingOpeningElement=opening1, RelatedBuildingElement=door),
    ])
    return IFC(entities)


def _run(model=None):
    return assemble_source_dossier(
        model or _fixture(), sha256="a" * 64, size_bytes=1000,
        length_unit="MILLIMETRE", unit_scale_to_meters=0.001,
    )


def test_source_dossier_counts_relations_without_inferring_opening_states():
    data = _run()
    assert data["source"]["unit_scale_to_meters"] == 0.001
    assert data["storeys"] == [
        {"elevation_m_declared": -7.3, "direct_contained_elements": 1, "associated_spaces": 0, "index": 1},
        {"elevation_m_declared": -4.0, "direct_contained_elements": 2, "associated_spaces": 1, "index": 2},
    ]
    assert data["openings"]["void_relations"] == 2
    assert data["openings"]["fill_relations"] == 1
    assert data["openings"]["voids_without_filling_relation"] == 1
    assert data["openings"]["voids_with_filling_relation"] == 1
    assert data["openings"]["host_class_counts"] == {"IFCSLAB": 1, "IFCWALLSTANDARDCASE": 1}
    assert data["openings"]["door_elements_without_filling_relation"] == 0
    assert "UNFILLED_VOID_RELATIONS_REQUIRE_REVIEW" in data["warnings"]
    assert "MEP_ENTITIES_NOT_IN_THIS_SOURCE" in data["warnings"]
    assert "SPACE_BOUNDARY_RELATIONS_ABSENT" in data["warnings"]
    assert "COORDINATE_PLACEMENTS_NOT_VERIFIED" in data["warnings"]
    assert (data["geometry_verdict"], data["mapping_verdict"], data["scientific_verdict"]) == (
        "NOT_EVALUATED", "NOT_EVALUATED", "INCONCLUSIVE",
    )


def test_source_dossier_is_deterministic_and_redacts_sensitive_data():
    a, b = _run(), _run()
    raw = json.dumps(a, sort_keys=True, ensure_ascii=False)
    assert raw == json.dumps(b, sort_keys=True, ensure_ascii=False)
    for forbidden in ("Sensitive", "PRIVATE-GUID", "PRIVATE_ROOM", "file_path", "ifc_local_to_model"):
        assert forbidden not in raw


def test_invalid_opening_and_duplicate_relation_stays_review_required():
    model = _fixture()
    opening = next(e for e in model.entities if e.is_a() == "IfcOpeningElement")
    wall = next(e for e in model.entities if e.is_a() == "IfcWallStandardCase")
    model.entities.append(Entity(15, "IfcRelVoidsElement", RelatedOpeningElement=opening, RelatingBuildingElement=wall))
    model.entities.append(Entity(16, "IfcRelFillsElement", RelatingOpeningElement=None, RelatedBuildingElement=wall))
    result = _run(model)
    assert result["openings"]["duplicate_void_opening_relations"] == 1
    assert result["openings"]["invalid_filling_relations"] == 1
    assert "INVALID_OR_DUPLICATED_OPENING_RELATIONS" in result["warnings"]
    assert result["mapping_verdict"] == "NOT_EVALUATED"


@pytest.mark.parametrize("scale", [0.0, -0.01, float("inf"), float("nan")])
def test_invalid_length_scale_fails_closed(scale):
    with pytest.raises(ValueError):
        assemble_source_dossier(
            _fixture(), sha256="a" * 64, size_bytes=10,
            length_unit="MILLIMETRE", unit_scale_to_meters=scale,
        )


def test_missing_storey_elevation_is_explicit():
    model = _fixture()
    model.entities[0].Elevation = None
    result = _run(model)
    assert result["storeys"][-1]["elevation_m_declared"] is None
    assert "STOREY_ELEVATION_NOT_DECLARED" in result["warnings"]


def test_invalid_source_sha_is_not_accepted():
    with pytest.raises(ValueError):
        assemble_source_dossier(
            _fixture(), sha256="wrong", size_bytes=10,
            length_unit="METRE", unit_scale_to_meters=1.0,
        )


def test_orphan_opening_and_fill_without_void_are_visible():
    model = _fixture()
    extra = Entity(17, "IfcOpeningElement")
    model.entities.append(extra)
    model.entities.append(Entity(
        18, "IfcRelFillsElement",
        RelatingOpeningElement=extra, RelatedBuildingElement=Entity(7, "IfcDoor"),
    ))
    result = _run(model)
    assert result["openings"]["opening_elements_without_void_relation"] == 1
    assert result["openings"]["filling_relations_without_void_relation"] == 1
    assert result["mapping_verdict"] == "NOT_EVALUATED"


def test_private_dossier_file_is_exclusive_and_not_overwritten(tmp_path):
    destination = tmp_path / "private" / "source-dossier.json"
    data = _run()
    write_source_dossier(destination, data)
    assert json.loads(destination.read_text(encoding="utf-8")) == data
    if __import__("os").name == "posix":
        assert destination.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        write_source_dossier(destination, {"malicious": True})
    assert json.loads(destination.read_text(encoding="utf-8")) == data


def test_destination_must_be_json(tmp_path):
    with pytest.raises(ValueError):
        write_source_dossier(tmp_path / "source.ifc", _run())


def test_public_opening_ifc_fixture_without_geometry():
    path = Path(__file__).resolve().parents[1] / "tests" / "baseline" / "fixtures" / "opening.ifc"
    result = inspect_source_dossier(path)
    assert result["source"]["ifc_schema"] == "IFC4"
    assert result["openings"]["void_relations"] == 1
    assert result["openings"]["fill_relations"] == 0
    assert result["openings"]["voids_without_filling_relation"] == 1
    assert "WallWithOpening" not in json.dumps(result)
    assert result["approval_status"] == "DRAFT"


def test_cli_generates_private_dossier_without_printing_model_path(tiny_ifc, tmp_path, capsys):
    from ifc_to_fds.cli import main

    path, _, _ = tiny_ifc
    destination = tmp_path / "private" / "source-dossier.json"
    assert main(["source-dossier", str(path), "-o", str(destination)]) == 0
    assert destination.is_file()
    assert str(path) not in capsys.readouterr().out
    assert json.loads(destination.read_text(encoding="utf-8"))["mapping_verdict"] == "NOT_EVALUATED"
