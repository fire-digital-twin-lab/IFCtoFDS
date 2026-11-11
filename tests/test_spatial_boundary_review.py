"""Kiểm thử A4: IFC spatial boundary là nguồn quan hệ, không là air-path."""

import json
import os
from pathlib import Path

import pytest

from ifc_to_fds.core.spatial_boundary_review import (
    assemble_spatial_boundary_review,
    inspect_spatial_boundary_review,
    save_spatial_boundary_review,
)


class Entity:
    def __init__(self, step_id, kind, **fields):
        self._step_id = step_id
        self._kind = kind
        self.GlobalId = f"PRIVATE-{step_id}"
        self.Name = f"PRIVATE-NAME-{step_id}"
        for key, value in fields.items():
            setattr(self, key, value)

    def id(self):
        return self._step_id

    def is_a(self):
        return self._kind


class Model:
    schema = "IFC2X3"

    def __init__(self, entities):
        self.entities = entities

    def by_type(self, name):
        return [e for e in self.entities if e.is_a() == name]


def _model():
    room1 = Entity(1, "IfcSpace")
    room2 = Entity(2, "IfcSpace")
    wall = Entity(3, "IfcWallStandardCase")
    boundary1 = Entity(
        4, "IfcRelSpaceBoundary",
        RelatingSpace=room1,
        RelatedBuildingElement=wall,
        PhysicalOrVirtualBoundary="PHYSICAL",
        InternalOrExternalBoundary="INTERNAL",
    )
    boundary2 = Entity(
        5, "IfcRelSpaceBoundary",
        RelatingSpace=room2,
        RelatedBuildingElement=None,
        PhysicalOrVirtualBoundary="VIRTUAL",
        InternalOrExternalBoundary="EXTERNAL",
    )
    return Model([room1, room2, wall, boundary1, boundary2])


def _report(model=None):
    return assemble_spatial_boundary_review(
        model or _model(), source_sha256="a" * 64
    )


def test_source_boundaries_are_not_promoted_to_airflow_connections():
    report = _report()
    assert report["space_count"] == 2
    assert report["boundary_relation_count"] == 2
    assert report["boundaries_without_known_relating_space"] == 0
    assert report["boundary_class_counts"] == {"IfcRelSpaceBoundary": 2}
    assert report["related_element_class_counts"] == {
        "IfcWallStandardCase": 1, "MISSING": 1,
    }
    first, second = report["space_review_queue"]
    assert first["space"]["step_id"] == 1
    assert first["boundary_relation_count"] == 1
    assert first["boundaries"][0]["related_element"]["ifc_type"] == "IfcWallStandardCase"
    assert first["boundaries"][0]["physical_or_virtual"] == "PHYSICAL"
    assert second["boundaries"][0]["physical_or_virtual"] == "VIRTUAL"
    assert "BOUNDARY_WITHOUT_RELATED_BUILDING_ELEMENT" in second["review_reasons"]
    assert all(x["airflow_connectivity"] == "NOT_EVALUATED" for x in report["space_review_queue"])
    assert all(x["human_review_status"] == "UNREVIEWED" for x in report["space_review_queue"])
    assert report["spatial_adjacency_verdict"] == "NOT_EVALUATED"
    assert report["airflow_verdict"] == "NOT_EVALUATED"
    assert report["review_approval"] == "NOT_GRANTED"
    assert report["scientific_verdict"] == "INCONCLUSIVE"


def test_ifc_spaces_without_any_boundaries_must_be_reviewed():
    model = _model()
    model.entities = [e for e in model.entities if e.is_a() == "IfcSpace"]
    result = _report(model)
    assert result["space_count"] == 2
    assert result["boundary_relation_count"] == 0
    assert "IFC_SPACE_BOUNDARY_RELATIONS_ABSENT" in result["warnings"]
    assert all("SPACE_WITHOUT_BOUNDARY_RELATIONS" in x["review_reasons"]
               for x in result["space_review_queue"])
    assert result["airflow_verdict"] == "NOT_EVALUATED"


def test_corresponding_boundary_is_not_evidence_for_open_air_path():
    model = _model()
    b1, b2 = [e for e in model.entities if e.is_a() == "IfcRelSpaceBoundary"]
    b1.CorrespondingBoundary = b2
    report = _report(model)
    a = report["space_review_queue"][0]
    assert "CORRESPONDING_BOUNDARY_REQUIRES_GEOMETRY_REVIEW" in a["review_reasons"]
    assert a["boundaries"][0]["corresponding_boundary"]["step_id"] == b2.id()
    assert a["airflow_connectivity"] == "NOT_EVALUATED"


def test_orphan_boundary_and_missing_host_are_reported_not_ignored():
    model = _model()
    model.entities.append(Entity(
        6, "IfcRelSpaceBoundary",
        RelatingSpace=None, RelatedBuildingElement=None,
    ))
    result = _report(model)
    assert result["boundaries_without_known_relating_space"] == 1
    assert "IFC_SPACE_BOUNDARIES_UNLINKED" in result["warnings"]
    assert result["related_element_class_counts"]["MISSING"] == 2
    assert result["mapping_verdict"] == "NOT_EVALUATED"


def test_duplicate_space_step_ids_fail_closed():
    model = _model()
    model.entities.append(Entity(1, "IfcSpace"))
    with pytest.raises(ValueError, match="duplicated"):
        _report(model)


def test_private_review_is_stable_exclusive_and_not_world_readable(tmp_path):
    data = _report()
    assert json.dumps(data, sort_keys=True) == json.dumps(_report(), sort_keys=True)
    output = tmp_path / "private" / "spatial-review.json"
    save_spatial_boundary_review(output, data)
    text = output.read_text(encoding="utf-8")
    assert "PRIVATE-1" in text  # File chỉ dùng trong máy cá nhân có quyền.
    assert "PRIVATE-NAME-1" not in text
    assert json.loads(text) == data
    if os.name == "posix":
        assert output.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        save_spatial_boundary_review(output, {"overwritten": True})
    assert json.loads(output.read_text(encoding="utf-8")) == data


def test_bad_sha_rejected():
    with pytest.raises(ValueError, match="source hash"):
        assemble_spatial_boundary_review(_model(), source_sha256="not-a-hash")


def test_real_public_ifc_fixture_does_not_invent_missing_spaces():
    path = Path(__file__).resolve().parents[1] / "tests" / "baseline" / "fixtures" / "opening.ifc"
    report = inspect_spatial_boundary_review(path)
    assert report["ifc_schema"] == "IFC4"
    assert report["space_count"] == 0
    assert report["boundary_relation_count"] == 0
    assert "NO_IFC_SPACES_IN_SOURCE" in report["warnings"]
    assert report["spatial_adjacency_verdict"] == "NOT_EVALUATED"


def test_cli_private_spatial_review_without_logging_file_path(tiny_ifc, tmp_path, capsys):
    from ifc_to_fds.cli import main

    file_path, _, _ = tiny_ifc
    output = tmp_path / "spatial-boundary-review.json"
    assert main(["spatial-boundary-review", str(file_path), "-o", str(output)]) == 0
    assert str(file_path) not in capsys.readouterr().out
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["review_approval"] == "NOT_GRANTED"
    assert result["airflow_verdict"] == "NOT_EVALUATED"
