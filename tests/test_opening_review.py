"""A3 — Kiểm thử queue opening và không tự chứng nhận đường khói."""

import json
from pathlib import Path

import pytest

from ifc_to_fds.core.opening_review import (
    assemble_opening_review,
    inspect_opening_review,
    save_opening_review,
)


class Entity:
    def __init__(self, step, kind, **attributes):
        self._step = step
        self._kind = kind
        self.GlobalId = f"PRIVATE-{step}"
        for key, value in attributes.items():
            setattr(self, key, value)

    def id(self):
        return self._step

    def is_a(self):
        return self._kind


class Model:
    schema = "IFC2X3"

    def __init__(self, entities):
        self.entities = entities

    def by_type(self, name):
        return [entity for entity in self.entities if entity.is_a() == name]


def _fixture():
    wall = Entity(1, "IfcWallStandardCase")
    slab = Entity(2, "IfcSlab")
    door = Entity(3, "IfcDoor")
    void1 = Entity(4, "IfcOpeningElement", Representation=object())
    void2 = Entity(5, "IfcOpeningElement", Representation=object())
    model = Model([
        wall, slab, door, void1, void2,
        Entity(6, "IfcRelVoidsElement", RelatingBuildingElement=wall, RelatedOpeningElement=void1),
        Entity(7, "IfcRelVoidsElement", RelatingBuildingElement=slab, RelatedOpeningElement=void2),
        Entity(8, "IfcRelFillsElement", RelatingOpeningElement=void1, RelatedBuildingElement=door),
    ])
    return model


def _report(model=None):
    return assemble_opening_review(model or _fixture(), source_sha256="a" * 64)


def test_unfilled_void_is_reviewed_not_assumed_airflow_path():
    data = _report()
    assert data["opening_count"] == 2
    assert data["void_relation_count"] == 2
    assert data["fill_relation_count"] == 1
    assert data["openings_with_fill_relation"] == 1
    assert data["openings_without_fill_relation"] == 1
    queue = data["opening_review_queue"]
    assert [x["opening"]["step_id"] for x in queue] == [4, 5]
    assert "NO_FILLING_RELATION" not in queue[0]["review_reasons"]
    assert "NO_FILLING_RELATION" in queue[1]["review_reasons"]
    assert queue[0]["hosts"][0]["ifc_type"] == "IfcWallStandardCase"
    assert queue[1]["hosts"][0]["ifc_type"] == "IfcSlab"
    assert queue[0]["fill_elements"][0]["ifc_type"] == "IfcDoor"
    assert all(x["physical_state"] == "UNKNOWN" for x in queue)
    assert all(x["airflow_connectivity"] == "NOT_EVALUATED" for x in queue)
    assert all(x["human_review_status"] == "UNREVIEWED" for x in queue)
    assert data["mapping_verdict"] == "NOT_EVALUATED"
    assert data["scientific_verdict"] == "INCONCLUSIVE"
    assert data["review_approval"] == "NOT_GRANTED"


def test_duplicate_voids_and_malformed_fills_are_visible():
    model = _fixture()
    o = next(e for e in model.entities if e.is_a() == "IfcOpeningElement")
    wall = next(e for e in model.entities if e.is_a() == "IfcWallStandardCase")
    model.entities += [
        Entity(9, "IfcRelVoidsElement", RelatedOpeningElement=o, RelatingBuildingElement=wall),
        Entity(10, "IfcRelFillsElement", RelatingOpeningElement=o, RelatedBuildingElement=None),
        Entity(11, "IfcRelFillsElement", RelatingOpeningElement=None, RelatedBuildingElement=wall),
    ]
    result = _report(model)
    assert result["unlinked_fill_relation_count"] == 1
    first = result["opening_review_queue"][0]
    assert first["void_relation_count"] == 2
    assert first["fill_relation_count"] == 2
    assert "MULTIPLE_VOID_RELATIONS" in first["review_reasons"]
    assert "MULTIPLE_FILLING_RELATIONS" in first["review_reasons"]
    assert "MISSING_FILL_ELEMENT" in first["review_reasons"]
    assert first["physical_state"] == "UNKNOWN"


def test_unhosted_opening_with_filling_does_not_become_approved():
    model = _fixture()
    opening = Entity(20, "IfcOpeningElement", Representation=None)
    model.entities += [
        opening,
        Entity(21, "IfcRelFillsElement", RelatingOpeningElement=opening, RelatedBuildingElement=Entity(3, "IfcDoor")),
    ]
    result = _report(model)
    item = result["opening_review_queue"][-1]
    assert "OPENING_WITHOUT_VOID_RELATION" in item["review_reasons"]
    assert "FILLING_WITHOUT_VOID_RELATION" in item["review_reasons"]
    assert "OPENING_HAS_NO_REPRESENTATION" in item["review_reasons"]
    assert result["review_approval"] == "NOT_GRANTED"


def test_unnamed_or_missing_fill_cannot_be_deduced_from_door_count():
    model = _fixture()
    model.entities.append(Entity(33, "IfcDoor", Name="DOOR_NOT_LINKED"))
    result = _report(model)
    assert result["opening_count"] == 2
    assert result["openings_without_fill_relation"] == 1
    assert "DOOR_NOT_LINKED" not in json.dumps(result)


def test_step_id_and_guids_preserved_only_in_private_output(tmp_path):
    target = tmp_path / "private" / "opening-review.json"
    data = _report()
    save_opening_review(target, data)
    raw = target.read_text(encoding="utf-8")
    assert "PRIVATE-4" in raw
    assert json.loads(raw) == data
    assert data["privacy_classification"] == "PRIVATE_SOURCE_IDENTIFIERS"
    if __import__("os").name == "posix":
        assert target.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        save_opening_review(target, {})
    assert json.loads(target.read_text(encoding="utf-8")) == data


def test_source_sha_must_be_valid():
    with pytest.raises(ValueError, match="source hash"):
        assemble_opening_review(_fixture(), source_sha256="invalid")


def test_real_public_opening_ifc_has_one_unfilled_void():
    path = Path(__file__).resolve().parents[1] / "tests" / "baseline" / "fixtures" / "opening.ifc"
    report = inspect_opening_review(path)
    assert report["ifc_schema"] == "IFC4"
    assert report["opening_count"] == 1
    assert report["void_relation_count"] == 1
    assert report["fill_relation_count"] == 0
    assert report["openings_without_fill_relation"] == 1
    assert report["mapping_verdict"] == "NOT_EVALUATED"


def test_cli_does_not_log_private_identifiers(tiny_ifc, tmp_path, capsys):
    from ifc_to_fds.cli import main

    path, _, _ = tiny_ifc
    output = tmp_path / "review.json"
    assert main(["opening-review", str(path), "-o", str(output)]) == 0
    printed = capsys.readouterr().out
    assert str(path) not in printed
    assert "GlobalId" not in printed
    assert json.loads(output.read_text(encoding="utf-8"))["review_approval"] == "NOT_GRANTED"
