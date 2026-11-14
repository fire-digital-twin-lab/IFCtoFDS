"""Unreliable georeference is reported; a model with several sites must say which storeys it means."""

from pathlib import Path

import ifcopenshell
import pytest

from ifc_to_fds.application.services.model_preparer import prepare_model
from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.pipeline import convert

TINY = Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc"
REVIT_DEFAULT = dict(RefLatitude=(42, 21, 31, 181945), RefLongitude=(-71, -3, -24, -263305))


def _with_sites(tmp_path, n, **coords):
    f = ifcopenshell.open(str(TINY))
    for k in range(n):
        f.create_entity("IfcSite", GlobalId=ifcopenshell.guid.new(), Name=f"Site {k}", **coords)
    path = tmp_path / "sites.ifc"
    f.write(str(path))
    return str(path)


def test_software_default_site_location_is_marked_unreliable(tmp_path):
    model, _ = extract_inventory(_with_sites(tmp_path, 1, **REVIT_DEFAULT))
    assert model.source.georeference["status"] == "SOFTWARE_DEFAULT_SITE_LOCATION"
    other, _ = extract_inventory(_with_sites(tmp_path, 1, RefLatitude=(21, 1, 0, 0), RefLongitude=(105, 50, 0, 0)))
    assert other.source.georeference is None


def test_default_location_becomes_an_informational_finding(tmp_path):
    result = convert([_with_sites(tmp_path, 1, **REVIT_DEFAULT)], output_directory=tmp_path / "out")
    found = [f for f in result["report"]["findings"] if f["category"] == "georeference"]
    assert found and found[0]["severity"] == "P2"
    assert result["status"] != "REJECTED"  # information only


def test_several_sites_require_an_explicit_scope(tmp_path):
    path = _with_sites(tmp_path, 3)
    with pytest.raises(ValueError, match="IfcSite"):
        prepare_model([path], {})
    prepare_model([path], {"scope": {"storeys": ["Ground"]}})  # an explicit scope is accepted
    prepare_model([_with_sites(tmp_path, 1)], {})  # one site needs none


def test_scope_guard_fails_before_any_geometry_is_built(tmp_path, monkeypatch):
    from ifc_to_fds.application.services import model_preparer

    def forbidden(*args, **kwargs):
        raise AssertionError("geometry/inventory work started before the scope check")

    monkeypatch.setattr(model_preparer, "load_sources", forbidden)
    with pytest.raises(ValueError, match="IfcSite"):
        prepare_model([_with_sites(tmp_path, 3)], {})
