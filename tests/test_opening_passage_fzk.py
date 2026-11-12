"""Hồi quy Boolean cho ba lỗ mở thật và một phép đo giải tích."""

from pathlib import Path

import pytest

from ifc_to_fds.application.services.model_preparer import prepare_model
from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.domain.scope.model import ScopeDecision
from ifc_to_fds.geometry.mesh import box_mesh
from ifc_to_fds.mapping.boundary import target_mesh
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation.metrics import SolidCandidateIndex, passage_metrics
from ifc_to_fds.validation.parser import parse_fds


def test_three_fzk_openings_preserve_serialized_free_volume(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "examples/AC20-FZK-Haus.ifc"
    monkeypatch.setenv("IFCFDS_GEOMETRY_CACHE", str(tmp_path / "cache"))
    deck, _ = serialize_fds(prepare_model([str(source)], {}))
    model = prepare_model([str(source)], {}, reference=True)
    reference = SolidCandidateIndex(
        target_mesh(element)
        for element in model.elements
        if element.mesh
        and element.role == "PHYSICAL"
        and element.mapping_strategy.value in ("OBST", "GEOM")
        and element.scope_decision in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
    )
    emitted = SolidCandidateIndex(
        record.mesh()
        for record in parse_fds(deck).primitives
        if record.kind in ("GEOM", "OBST")
    )
    opening_ids = (22174, 31539, 31607)
    openings = {
        opening.opening_step_id: opening.mesh
        for element in model.elements
        for opening in element.openings
        if opening.opening_step_id in opening_ids
    }
    assert set(openings) == set(opening_ids)
    evidence = [
        passage_metrics(reference, emitted, openings[step_id]) for step_id in opening_ids
    ]
    assert [p["normalized_symmetric_difference"] for p in evidence] == [0, 0, 0]
    assert [p["source_free_components"] for p in evidence] == [10, 4, 14]
    assert [p["output_free_components"] for p in evidence] == [10, 4, 14]


def test_equal_free_volume_and_component_count_do_not_hide_moved_blocker(box_model):
    opening = box_model.elements[0].mesh  # 2 m × 1 m × 3 m
    first = box_mesh(BoundingBox(xmin=0.25, xmax=0.5, ymin=0, ymax=1, zmin=0, zmax=3))
    second = box_mesh(BoundingBox(xmin=1.5, xmax=1.75, ymin=0, ymax=1, zmin=0, zmax=3))
    evidence = passage_metrics([first], [second], opening)
    assert evidence["source_free_volume_m3"] == pytest.approx(5.25)
    assert evidence["output_free_volume_m3"] == pytest.approx(5.25)
    assert evidence["source_free_components"] == evidence["output_free_components"] == 2
    assert evidence["normalized_symmetric_difference"] == pytest.approx(0.25)
