"""IfcAxis2Placement3D with a RefDirection that is not perpendicular to Axis.

IFC derives X by projecting RefDirection onto the plane normal to Axis. The
matrix must stay a rotation (RᵀR = I, det = +1) and agree with the native
OpenCASCADE geometry, which applies the same projection.
"""

from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pytest

from ifc_to_fds.core.placement import extract_placement, is_rigid_rotation

TINY = Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc"


def _model(ref_direction):
    f = ifcopenshell.open(str(TINY))
    f.by_id(27).DirectionRatios = tuple(float(x) for x in ref_direction)  # wall placement RefDirection
    return f


def _matrix(f):
    wall = f.by_type("IfcWall")[0]
    p = extract_placement(wall, 1.0)
    return p, np.asarray(p.get("ifc_local_to_model", np.eye(4).ravel().tolist())).reshape(4, 4)


def _native_bounds(f):
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    shape = ifcopenshell.geom.create_shape(settings, f.by_type("IfcWall")[0])
    v = np.asarray(shape.geometry.verts).reshape(-1, 3)
    return v.min(axis=0), v.max(axis=0)


def test_oblique_ref_direction_is_orthonormalised_like_ifc():
    placement, matrix = _matrix(_model((1.0, 0.0, 1.0)))
    clean_placement, clean = _matrix(_model((1.0, 0.0, 0.0)))
    assert placement["status"] == "CONFIRMED"
    assert is_rigid_rotation(matrix[:3, :3])
    assert np.linalg.det(matrix[:3, :3]) == pytest.approx(1.0, abs=1e-9)
    # Projecting (1,0,1) off Z=(0,0,1) leaves X=(1,0,0): same frame as the clean model.
    assert matrix == pytest.approx(clean, abs=1e-9)


def test_oblique_ref_direction_matches_native_geometry_bounds():
    lo, hi = _native_bounds(_model((1.0, 0.0, 1.0)))
    clean_lo, clean_hi = _native_bounds(_model((1.0, 0.0, 0.0)))
    assert lo == pytest.approx(clean_lo, abs=1e-9)
    assert hi == pytest.approx(clean_hi, abs=1e-9)
    # The provenance matrix applied to the local extrusion box reproduces those bounds.
    _, matrix = _matrix(_model((1.0, 0.0, 1.0)))
    corners = np.array([[x, y, z, 1.0] for x in (0, 2) for y in (0, 1) for z in (0, 3)])
    world = (matrix @ corners.T).T[:, :3]
    assert world.min(axis=0) == pytest.approx(lo, abs=1e-9)
    assert world.max(axis=0) == pytest.approx(hi, abs=1e-9)


def test_ref_direction_parallel_to_axis_is_not_confirmed():
    placement, _ = _matrix(_model((0.0, 0.0, 1.0)))
    assert placement["status"] == "UNVERIFIED"


def test_is_rigid_rotation_rejects_shear_scale_and_reflection():
    assert is_rigid_rotation(np.eye(3))
    assert not is_rigid_rotation(np.array([[1, 0, 0.7], [0, 1, 0], [0, 0, 1.0]]))
    assert not is_rigid_rotation(2.0 * np.eye(3))
    assert not is_rigid_rotation(np.diag([1.0, 1.0, -1.0]))
    assert not is_rigid_rotation(np.full((3, 3), np.nan))
