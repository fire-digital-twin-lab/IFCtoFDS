"""A2: oracle tọa độ, matrix rigid, unit conversion và privacy."""

import json
from pathlib import Path

import numpy as np
import pytest

from ifc_to_fds.core import coordinate_preflight as cp


SHA = "a" * 64


class Placement:
    def __init__(self, step_id, matrix, parent=None, kind="IfcLocalPlacement"):
        self.step_id = step_id
        self.matrix = matrix
        self.PlacementRelTo = parent
        self.kind = kind

    def id(self):
        return self.step_id

    def is_a(self, name=None):
        return self.kind == name if name else self.kind


class Product:
    def __init__(self, step_id, placement):
        self.step_id = step_id
        self.ObjectPlacement = placement
        self.GlobalId = "PRIVATE-GUID"
        self.Name = "PRIVATE-building-name"

    def id(self):
        return self.step_id


class IFC:
    schema = "IFC2X3"

    def __init__(self, products):
        self.products = products

    def by_type(self, name):
        if name != "IfcProduct":
            raise AssertionError("No geometry or other source type may be loaded")
        return list(self.products)


def _matrix(position=(0.0, 0.0, 0.0), angle_degrees=0.0):
    angle = np.deg2rad(angle_degrees)
    matrix = np.eye(4, dtype=float)
    c, s = np.cos(angle), np.sin(angle)
    matrix[:2, :2] = [[c, -s], [s, c]]
    matrix[:3, 3] = position
    return matrix


@pytest.fixture(autouse=True)
def stub_ifc_placement_matrix(monkeypatch):
    monkeypatch.setattr(cp, "get_local_placement", lambda p: p.matrix)


def _preflight(products, scale=1.0, limit=25000):
    return cp.summarize_coordinate_placements(
        IFC(products), source_sha256=SHA, length_unit="METRE",
        scale_to_meters=scale, max_products=limit,
    )


def test_large_metric_translation_is_flagged_without_exposing_coordinates():
    product = Product(1, Placement(2, _matrix((2_500_000, -4_000_000, 0))))
    result = _preflight([product], scale=0.001)
    assert result["maximum_absolute_translation_band_m"] == "1000_TO_10000_M"
    assert "LARGE_COORDINATE_MAGNITUDE_REQUIRES_REVIEW" in result["warnings"]
    assert result["placement_status_counts"] == {"READABLE_RIGID": 1}
    assert result["placement_verdict"] == "REVIEW_REQUIRED"
    assert result["geometry_verdict"] == "NOT_EVALUATED"
    serialized = json.dumps(result)
    for sensitive in ("PRIVATE-GUID", "PRIVATE-building-name", "-4000000", "2500000", "rebase_vector", "matrix"):
        assert sensitive not in serialized


def test_mm_to_m_scale_does_not_modify_rotation_or_apply_double_rebase():
    original = _matrix((2_000_000, -1_000_000, -7300), angle_degrees=90.0)
    placement = Placement(9, original.copy())
    product = Product(1, placement)
    scaled_mm = _preflight([product], scale=0.001)
    equivalent_m = _preflight(
        [Product(1, Placement(9, _matrix((2000, -1000, -7.3), 90)))],
        scale=1.0,
    )
    assert scaled_mm["maximum_absolute_translation_band_m"] == equivalent_m[
        "maximum_absolute_translation_band_m"
    ]
    assert scaled_mm["placement_status_counts"] == equivalent_m["placement_status_counts"]
    np.testing.assert_array_equal(placement.matrix, original)
    assert "WORLD_TO_LOCAL_REBASE_NOT_EXECUTED" in scaled_mm["warnings"]


def test_cycle_rejected_before_calling_ifcopenshell(monkeypatch):
    p = Placement(9, _matrix())
    p.PlacementRelTo = p
    def fail_if_called(_):
        raise AssertionError("cyclic placement must never reach IfcOpenShell")
    monkeypatch.setattr(cp, "get_local_placement", fail_if_called)
    report = _preflight([Product(1, p)])
    assert report["placement_status_counts"] == {"CYCLE_OR_INVALID_ID": 1}
    assert "PRODUCT_PLACEMENT_INVALID_OR_UNSUPPORTED" in report["warnings"]


@pytest.mark.parametrize(
    ("matrix", "expected"),
    [
        (np.zeros((3, 3)), "NONFINITE_OR_BAD_SHAPE"),
        (_matrix((float("inf"), 0.0, 0.0)), "NONFINITE_OR_BAD_SHAPE"),
        (np.diag([-1, 1, 1, 1]), "NON_RIGID"),
        (np.diag([2, 1, 1, 1]), "NON_RIGID"),
        (np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 2]]), "NON_RIGID"),
    ],
)
def test_rejects_invalid_rigid_matrices(matrix, expected):
    report = _preflight([Product(1, Placement(2, matrix))])
    assert report["placement_status_counts"] == {expected: 1}
    assert "PRODUCT_PLACEMENT_INVALID_OR_UNSUPPORTED" in report["warnings"]


def test_unsupported_placement_and_missing_placement_are_not_silent():
    report = _preflight([
        Product(1, Placement(5, _matrix(), kind="IfcGridPlacement")),
        Product(2, None),
    ])
    assert report["placement_status_counts"] == {"MISSING": 1, "UNSUPPORTED": 1}
    assert "PRODUCT_PLACEMENT_MISSING" in report["warnings"]
    assert report["scientific_verdict"] == "INCONCLUSIVE"


def test_scan_limit_marks_partial_results_and_selects_smallest_step_ids():
    products = [
        Product(30, Placement(10, _matrix((5000000, 0, 0)))),
        Product(10, Placement(11, _matrix())),
        Product(20, Placement(12, _matrix())),
    ]
    report = _preflight(products, limit=2)
    assert report["total_products"] == 3
    assert report["examined_products"] == 2
    assert report["maximum_absolute_translation_band_m"] == "BELOW_100_M"
    assert "PLACEMENT_SCAN_INCOMPLETE" in report["warnings"]


@pytest.mark.parametrize("limit", [0, -1, True, 2.5])
def test_invalid_scan_limit_fails_closed(limit):
    with pytest.raises(ValueError, match="max_products"):
        _preflight([], limit=limit)


@pytest.mark.parametrize("scale", [0.0, -1.0, float("nan"), float("inf")])
def test_nonfinite_or_invalid_units_fail_closed(scale):
    with pytest.raises(ValueError, match="scale"):
        _preflight([], scale=scale)


def test_extreme_unit_scale_overflow_is_not_categorized_as_finite():
    report = _preflight(
        [Product(1, Placement(2, _matrix((1e308, 0, 0))))],
        scale=10.0,
    )
    assert report["placement_status_counts"] == {"NONFINITE_TRANSLATION_M": 1}
    assert report["maximum_absolute_translation_band_m"] == "BELOW_100_M"
    assert "PRODUCT_PLACEMENT_INVALID_OR_UNSUPPORTED" in report["warnings"]


def test_public_ifc_fixture_integration_preserves_private_output(tmp_path, monkeypatch):
    monkeypatch.undo()
    path = Path(__file__).resolve().parents[1] / "tests" / "baseline" / "fixtures" / "opening.ifc"
    report = cp.inspect_coordinate_file(path)
    assert report["ifc_schema"] == "IFC4"
    assert report["total_products"] >= 2
    assert report["geometry_verdict"] == "NOT_EVALUATED"
    target = tmp_path / "private" / "coordinate-preflight.json"
    cp.save_coordinate_preflight(target, report)
    assert json.loads(target.read_text(encoding="utf-8")) == report


def test_cli_preflight_writes_redacted_report(tiny_ifc, tmp_path, monkeypatch, capsys):
    from ifc_to_fds.cli import main

    monkeypatch.undo()
    file_path, _, _ = tiny_ifc
    target = tmp_path / "coordinate-preflight.json"
    assert main(["coordinate-preflight", str(file_path), "-o", str(target)]) == 0
    stdout = capsys.readouterr().out
    assert str(file_path) not in stdout
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["geometry_verdict"] == "NOT_EVALUATED"
    assert result["approval_status"] == "DRAFT"
