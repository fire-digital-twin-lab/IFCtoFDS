"""Reject native geometry whose observed length scale disagrees with the IFC."""

from types import SimpleNamespace

import ifcopenshell.api.geometry
import ifcopenshell.api.root
import numpy as np
import pytest

from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.geometry import engine


@pytest.fixture
def millimetre_wall(tiny_ifc):
    path, file, wall = tiny_ifc
    # Keep the existing 2 x 1 x 3 metre wall, expressing its source lengths in mm.
    unit = file.by_type("IfcSIUnit")[0]
    unit.Prefix = "MILLI"
    representation = ifcopenshell.api.geometry.add_wall_representation(
        file, context=file.by_type("IfcGeometricRepresentationSubContext")[0],
        length=2.0, height=3.0, thickness=1.0,
    )
    wall.Representation.Representations = (representation,)
    file.write(str(path))
    model, source = extract_inventory(str(path))
    assert model.source.unit_scale_to_meters == 0.001
    return model, source, wall.id()


@pytest.mark.parametrize("declared,converted,original", [
    (0.001, 3.0, 3000.0),
    (1.0, 3.0, 3.0),
    (0.0254, 0.762, 30.0),
    (0.3048, 0.9144, 3.0),
    (0.001, 3.000002, 3000.0),
    (0.001, 3.03, 3000.0),  # 1% tessellation noise between the two probes is not a unit error
])
def test_matching_length_scales(declared, converted, original):
    engine.check_kernel_length_scale(declared, converted, original)


@pytest.mark.parametrize("declared,converted,original", [
    (0.001, 3000.0, 3000.0),  # millimetre declared, nothing applied
    (0.9144, 3.0, 3.0),  # yard declared, metre applied: the smallest real unit error (9%)
    (0.001, 3.3, 3000.0),  # 10% off
])
def test_mismatching_length_scales(declared, converted, original):
    with pytest.raises(ValueError, match="declared.*native.*rejected.*wrong.scale"):
        engine.check_kernel_length_scale(declared, converted, original)


@pytest.mark.parametrize("declared,converted,original", [
    (0.001, 0.0, 3000.0), (0.001, 3.0, 0.0),
    (0.001, float("nan"), 3000.0), (0.001, 3.0, float("inf")),
    (float("inf"), 3.0, 3000.0), (0.001, -3.0, 3000.0),
])
def test_unmeasurable_length_scales_do_not_reject(declared, converted, original):
    engine.check_kernel_length_scale(declared, converted, original)


def test_consistent_millimetre_geometry_passes(millimetre_wall):
    model, source, step = millimetre_wall
    engine.process_model_geometry(model, source)
    wall = next(e for e in model.elements if e.step_id == step)
    assert np.ptp(wall.mesh.vertices, axis=0) == pytest.approx([2.0, 1.0, 3.0])


def test_unscaled_kernel_geometry_is_rejected(millimetre_wall, monkeypatch):
    model, source, step = millimetre_wall
    create_shape = engine.ifcopenshell.geom.create_shape

    def unscaled_shape(settings, product):
        shape = create_shape(settings, product)
        # Simulate a broken kernel: convert-back-units changes nothing.
        vertices = np.asarray(shape.geometry.verts)
        if settings.get("convert-back-units"):
            vertices = vertices * 0.001
        return SimpleNamespace(geometry=SimpleNamespace(verts=vertices.tolist()))

    monkeypatch.setattr(engine.ifcopenshell.geom, "create_shape", unscaled_shape)
    with pytest.raises(ValueError, match="declared.*0.001.*native.*1.*rejected.*wrong.scale"):
        engine.process_model_geometry(model, source)


def test_probe_runs_once_for_multiple_products(millimetre_wall, monkeypatch):
    model, source, step = millimetre_wall
    other = ifcopenshell.api.root.create_entity(source, ifc_class="IfcWall", name="Second")
    other.Representation = source.by_type("IfcWall")[0].Representation
    wall = next(e for e in model.elements if e.step_id == step)
    model.elements.append(wall.model_copy(update={"step_id": other.id()}))
    create_shape = engine.ifcopenshell.geom.create_shape
    calls = []

    def counted_shape(settings, product):
        calls.append(product.id())
        return create_shape(settings, product)

    monkeypatch.setattr(engine.ifcopenshell.geom, "create_shape", counted_shape)
    engine.process_model_geometry(model, source)
    assert len(calls) == 1


def test_unavailable_probe_does_not_reject(millimetre_wall, monkeypatch):
    model, source, step = millimetre_wall

    def unavailable_shape(*args):
        raise RuntimeError("unit probe unavailable")

    monkeypatch.setattr(engine.ifcopenshell.geom, "create_shape", unavailable_shape)
    engine.process_model_geometry(model, source)
    wall = next(e for e in model.elements if e.step_id == step)
    assert wall.mesh.vertices
    assert any("unit probe unavailable" in note for note in wall.validation_notes)


def test_no_geometry_does_not_probe(box_model, monkeypatch):
    def forbidden(*args):
        raise AssertionError("No geometry should be created")

    box_model.elements[0].has_3d_geometry = False
    monkeypatch.setattr(engine.ifcopenshell.geom, "create_shape", forbidden)
    engine.process_model_geometry(box_model, None)
