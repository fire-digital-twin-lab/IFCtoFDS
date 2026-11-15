"""Instanced native geometry: local tessellation plus a numpy placement equals world tessellation."""

from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pytest
import trimesh

from ifc_to_fds.geometry.engine import (
    create_geom_settings,
    prepare_source_mesh,
    transformed_mesh_arrays,
    world_mesh_from_shape,
)
from ifc_to_fds.geometry.mesh import as_trimesh, valid_solid

FIXTURES = Path(__file__).parent / "baseline" / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def _box():
    b = trimesh.creation.box(extents=(1, 2, 3))
    return b.vertices.astype(float), b.faces.astype(np.int32)


def test_rotation_translation_applied_in_float64():
    v, f = _box()
    m = np.eye(4)
    m[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    m[:3, 3] = [5.0e5, 2.0e6, 3.0]
    world, faces = transformed_mesh_arrays(v, f, m)
    assert np.allclose(world, v @ m[:3, :3].T + m[:3, 3], atol=0, rtol=0)
    assert np.array_equal(faces, f)  # proper rotation keeps the winding
    assert trimesh.Trimesh(world, faces, process=False).volume == pytest.approx(6.0)


def test_mirroring_matrix_reverses_winding_to_keep_outward_normals():
    v, f = _box()
    m = np.diag([-1.0, 1.0, 1.0, 1.0])
    world, faces = transformed_mesh_arrays(v, f, m)
    mirrored = trimesh.Trimesh(world, faces, process=False)
    assert mirrored.is_winding_consistent and mirrored.volume == pytest.approx(6.0)  # not -6


def _products(ifc):
    return [p for p in ifc.by_type("IfcProduct") if p.Representation]


@pytest.mark.parametrize(
    "path",
    [FIXTURES / "tiny.ifc", FIXTURES / "opening.ifc", ROOT / "examples" / "IfcOpenShell-Duplex.ifc"],
)
def test_instanced_iteration_matches_world_tessellation(path):
    ifc = ifcopenshell.open(str(path))
    products = _products(ifc)
    world_settings = create_geom_settings()
    local_settings = create_geom_settings(local=True)
    cache = {}
    iterator = ifcopenshell.geom.iterator(local_settings, ifc, 2, include=products)
    seen = 0
    assert iterator.initialize()
    while True:
        shape = iterator.get()
        product = ifc.by_id(shape.id)
        instanced, _ = prepare_source_mesh(world_mesh_from_shape(shape, cache))
        native = ifcopenshell.geom.create_shape(world_settings, product)
        reference, _ = prepare_source_mesh(
            __import__("ifc_to_fds.geometry.engine", fromlist=["mesh_from_geometry"]).mesh_from_geometry(native.geometry)
        )
        a, b = as_trimesh(instanced), as_trimesh(reference)
        assert valid_solid(instanced) == valid_solid(reference)
        assert np.allclose(a.bounds, b.bounds, atol=1e-9)
        assert a.volume == pytest.approx(b.volume, abs=1e-9)
        seen += 1
        if not iterator.next():
            break
    assert seen >= 1
