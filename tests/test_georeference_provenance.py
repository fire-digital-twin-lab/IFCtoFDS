"""IfcMapConversion is recorded as provenance; it must not move the simulation frame."""

import math
from pathlib import Path

import ifcopenshell
import pytest

from ifc_to_fds.core.inventory import extract_inventory

TINY = Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc"


def _georeferenced(tmp_path):
    f = ifcopenshell.open(str(TINY))
    context = f.by_type("IfcGeometricRepresentationContext")[0]
    crs = f.create_entity("IfcProjectedCRS", Name="EPSG:32648")
    f.create_entity(
        "IfcMapConversion", SourceCRS=context, TargetCRS=crs, Eastings=600000.0, Northings=2000000.0,
        OrthogonalHeight=12.5, XAxisAbscissa=math.cos(math.radians(30)), XAxisOrdinate=math.sin(math.radians(30)), Scale=1.0,
    )
    path = tmp_path / "geo.ifc"
    f.write(str(path))
    return str(path)


def test_map_conversion_is_recorded_without_moving_geometry(tmp_path):
    plain, _ = extract_inventory(str(TINY))
    model, _ = extract_inventory(_georeferenced(tmp_path))
    geo = model.source.georeference
    assert geo["crs"] == "EPSG:32648"
    assert (geo["eastings"], geo["northings"], geo["orthogonal_height"]) == (600000.0, 2000000.0, 12.5)
    assert geo["rotation_deg"] == pytest.approx(30.0)
    assert model.model_bounds == plain.model_bounds  # engineering frame, not map coordinates


def test_model_without_map_conversion_has_no_georeference():
    model, _ = extract_inventory(str(TINY))
    assert model.source.georeference is None
