"""Empirical adversarial stress test harness for Milestone 4 (P1 Implementation).

Orchestrated by Challenger 1 (critic/specialist).
Empirically tests:
1. Rebase Provenance Stress:
   - Models with massive coordinate shifts (UTM zone x > 500,000 m).
   - Massive negative coordinates (x < -500,000 m).
   - Sub-millimeter coordinate shifts (dx = 0.5 mm, dx = 0.1 mm).
   - Verification that any local point transformed by placement matrix exactly
     equals rebased vertex coordinate within 10^-9 m.
   - Validation across all matrix representations (1D list, 2D list, 1D ndarray, 2D ndarray).
   - Provenance propagation across elements, openings, ports, transforms, bounding boxes.

2. Adaptive CAD Tolerance Stress:
   - Micro-gaps (10^-7 to 10^-6 m) welded into closed manifolds.
   - Strict mode vs adaptive mode false-rejection reproduction.
   - Large gaps (10^-3 m / 1 mm) remain open and are refused.
   - Non-manifold meshes (T-junctions, non-orientable shells).
   - Sliver triangles: collapsing edges shorter than CAD tolerance rejected safely.
   - Volume preservation gate: thin structures violating >99.9% volume ratio refused.
   - Full integration with CanonicalElement and GeometryStatus.

3. SQLite WAL Persistence & Orphan Recovery:
   - WAL pragmas, crash recovery of RUNNING jobs, multi-thread durability.
"""

from typing import Sequence
import math
from pathlib import Path
import json
import sqlite3
import threading
import time
import numpy as np
import pytest

from ifc_to_fds.core.canonical import (
    BoundingBox,
    CanonicalElement,
    CanonicalModel,
    OpeningReference,
    PortReference,
    TriangleMesh,
)
from ifc_to_fds.core.federation import (
    _translate_matrix_4x4,
    rebase_model_to_origin,
)
from ifc_to_fds.domain.bim import GeometryStatus
from ifc_to_fds.domain.source.model import SourceMetadata
from ifc_to_fds.geometry.mesh import inspect_mesh_quality
from ifc_to_fds.geometry.normalization import (
    CAD_TOLERANCE_M,
    MAX_CAD_DISPLACEMENT_M,
    MAX_DISPLACEMENT_M,
    _compute_mesh_volume,
    normalize_element_geometry,
    normalize_source_mesh,
)
from ifc_to_fds.adapters.jobs.repository import JobRepository


# ===========================================================================
# HELPERS
# ===========================================================================


def _make_source_metadata(source_id="src1", filename="test.ifc"):
    return SourceMetadata(
        source_id=source_id,
        filename=filename,
        file_path=filename,
        file_hash_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        file_size_bytes=1024,
        schema_version="IFC4",
    )


def _create_rotation_matrix_xyz(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    """Create a 3x3 rotation matrix for arbitrary Euler angles."""
    ax, ay, az = np.radians([rx_deg, ry_deg, rz_deg])
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(ax), -np.sin(ax)],
        [0, np.sin(ax), np.cos(ax)],
    ])
    Ry = np.array([
        [np.cos(ay), 0, np.sin(ay)],
        [0, 1, 0],
        [-np.sin(ay), 0, np.cos(ay)],
    ])
    Rz = np.array([
        [np.cos(az), -np.sin(az), 0],
        [np.sin(az), np.cos(az), 0],
        [0, 0, 1],
    ])
    return Rz @ Ry @ Rx


def _create_affine_matrix(
    translation: Sequence[float] = (0.0, 0.0, 0.0),
    rotation_deg: Sequence[float] = (0.0, 0.0, 0.0),
    scale: Sequence[float] = (1.0, 1.0, 1.0),
) -> np.ndarray:
    """Create a 4x4 affine matrix acting on metre-valued column vectors."""
    R = _create_rotation_matrix_xyz(*rotation_deg)
    S = np.diag(scale)
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = R @ S
    M[:3, 3] = translation
    return M


def _build_cube_mesh(origin=(0.0, 0.0, 0.0), size=(1.0, 1.0, 1.0)) -> TriangleMesh:
    """Generate a clean 12-triangle closed manifold cube mesh."""
    x0, y0, z0 = origin
    dx, dy, dz = size
    vertices = [
        [x0, y0, z0],
        [x0 + dx, y0, z0],
        [x0 + dx, y0 + dy, z0],
        [x0, y0 + dy, z0],
        [x0, y0, z0 + dz],
        [x0 + dx, y0, z0 + dz],
        [x0 + dx, y0 + dy, z0 + dz],
        [x0, y0 + dy, z0 + dz],
    ]
    faces = [
        [0, 2, 1], [0, 3, 2],  # Bottom (-Z)
        [4, 5, 6], [4, 6, 7],  # Top (+Z)
        [0, 1, 5], [0, 5, 4],  # Front (-Y)
        [2, 3, 7], [2, 7, 6],  # Back (+Y)
        [0, 4, 7], [0, 7, 3],  # Left (-X)
        [1, 2, 6], [1, 6, 5],  # Right (+X)
    ]
    return TriangleMesh(vertices=vertices, faces=faces)


# ===========================================================================
# 1. EMPIRICAL CHALLENGES: REBASE PROVENANCE STRESS
# ===========================================================================


class TestRebaseProvenanceStress:
    """Rigorous empirical stress testing of coordinate rebase and placement provenance."""

    def test_utm_massive_coordinate_shift_precision_within_1e9(self):
        """Stress-test UTM zone coordinate shifts (x > 500,000 m).

        Verify that any local point transformed by placement matrix exactly equals
        rebased vertex coordinate within 10^-9 m.
        """
        # UTM Zone 48N coordinate shift (Vietnam / Hanoi region: x ~ 584,321 m, y ~ 2,324,567 m)
        world_translation = [584321.456789, 2324567.890123, 125.6789]
        local_vertices = np.array([
            [0.0, 0.0, 0.0],
            [2.5, 0.0, 0.0],
            [2.5, 4.0, 0.0],
            [0.0, 4.0, 0.0],
            [0.0, 0.0, 3.2],
            [2.5, 0.0, 3.2],
            [2.5, 4.0, 3.2],
            [0.0, 4.0, 3.2],
        ], dtype=np.float64)

        # Apply rotation (e.g., building orientation at 37.5 degrees)
        M_world = _create_affine_matrix(
            translation=world_translation,
            rotation_deg=(0.0, 0.0, 37.5),
            scale=(1.0, 1.0, 1.0),
        )

        # Transform local vertices to world coordinates
        homo_local = np.hstack([local_vertices, np.ones((len(local_vertices), 1))])
        world_vertices = (M_world @ homo_local.T).T[:, :3]

        element = CanonicalElement(
            step_id=101,
            global_id="GLOBAL_WALL_UTM_01",
            ifc_type="IfcWall",
            name="UTM Boundary Wall",
            mesh=TriangleMesh(vertices=world_vertices.tolist(), faces=[[0, 1, 2]]),
            placement=dict(
                status="CONFIRMED",
                effective_world=M_world.ravel().tolist(),
                model_to_common_world=np.eye(4).ravel().tolist(),
                ifc_local_to_model=M_world.ravel().tolist(),
            ),
            transform=M_world.ravel().tolist(),
            bounding_box=BoundingBox(
                xmin=float(world_vertices[:, 0].min()),
                xmax=float(world_vertices[:, 0].max()),
                ymin=float(world_vertices[:, 1].min()),
                ymax=float(world_vertices[:, 1].max()),
                zmin=float(world_vertices[:, 2].min()),
                zmax=float(world_vertices[:, 2].max()),
            ),
        )

        model = CanonicalModel(
            schema_version="0.5.0",
            source=_make_source_metadata(),
            elements=[element],
            model_bounds=BoundingBox(
                xmin=element.bounding_box.xmin,
                xmax=element.bounding_box.xmax,
                ymin=element.bounding_box.ymin,
                ymax=element.bounding_box.ymax,
                zmin=element.bounding_box.zmin,
                zmax=element.bounding_box.zmax,
            ),
        )

        # Execute automated rebase
        rebased_model, rebase_vec = rebase_model_to_origin(model, auto_rebase=True)
        assert rebase_vec[0] > 500000.0, f"Expected UTM shift > 500,000 m, got {rebase_vec[0]}"
        assert rebase_vec[1] > 2000000.0, f"Expected UTM shift > 2,000,000 m, got {rebase_vec[1]}"

        # Retrieve rebased provenance matrix and mesh vertices
        rebased_elem = rebased_model.elements[0]
        rebased_vertices = np.array(rebased_elem.mesh.vertices)
        M_rebased = np.array(rebased_elem.placement["effective_world"]).reshape(4, 4)
        M_transform = np.array(rebased_elem.transform).reshape(4, 4)

        # 1. Verify that local points transformed by rebased placement matrix exactly
        #    equal rebased mesh vertices within 10^-9 m.
        rebased_from_provenance = (M_rebased @ homo_local.T).T[:, :3]
        max_err_provenance = np.max(np.abs(rebased_from_provenance - rebased_vertices))
        assert max_err_provenance <= 1e-9, (
            f"Provenance drift exceeded tolerance: {max_err_provenance:.2e} m > 1e-9 m"
        )

        # 2. Verify transform matrix consistency within 10^-9 m
        rebased_from_transform = (M_transform @ homo_local.T).T[:, :3]
        max_err_transform = np.max(np.abs(rebased_from_transform - rebased_vertices))
        assert max_err_transform <= 1e-9, (
            f"Transform drift exceeded tolerance: {max_err_transform:.2e} m > 1e-9 m"
        )

        # 3. Test 1,000 randomly sampled local points inside bounding box
        np.random.seed(42)
        random_local_pts = np.random.uniform(
            low=[0.0, 0.0, 0.0],
            high=[2.5, 4.0, 3.2],
            size=(1000, 3),
        )
        homo_random = np.hstack([random_local_pts, np.ones((1000, 1))])
        expected_rebased_random = (M_world @ homo_random.T).T[:, :3] - np.array(rebase_vec)
        actual_rebased_random = (M_rebased @ homo_random.T).T[:, :3]

        max_random_err = np.max(np.abs(expected_rebased_random - actual_rebased_random))
        assert max_random_err <= 1e-9, (
            f"Random point local-to-world provenance error {max_random_err:.2e} m > 1e-9 m"
        )

    def test_massive_negative_coordinates_rebase_provenance(self):
        """Stress-test massive negative georeferenced coordinates (x < -500,000 m)."""
        # Coordinates in negative coordinate reference systems
        neg_translation = [-789123.456, -1456789.012, -450.5]
        local_pts = np.array([
            [-10.0, -10.0, -5.0],
            [10.0, -10.0, -5.0],
            [10.0, 10.0, 5.0],
            [-10.0, 10.0, 5.0],
        ], dtype=np.float64)

        M_world = _create_affine_matrix(
            translation=neg_translation,
            rotation_deg=(12.0, -25.0, 45.0),
            scale=(1.5, 0.8, 2.0),
        )

        homo_local = np.hstack([local_pts, np.ones((len(local_pts), 1))])
        world_pts = (M_world @ homo_local.T).T[:, :3]

        element = CanonicalElement(
            step_id=202,
            global_id="GLOBAL_COL_NEG_02",
            ifc_type="IfcColumn",
            mesh=TriangleMesh(vertices=world_pts.tolist(), faces=[[0, 1, 2], [0, 2, 3]]),
            placement=dict(
                status="CONFIRMED",
                effective_world=M_world.ravel().tolist(),
                model_to_common_world=np.eye(4).ravel().tolist(),
            ),
            transform=M_world.ravel().tolist(),
            bounding_box=BoundingBox(
                xmin=float(world_pts[:, 0].min()),
                xmax=float(world_pts[:, 0].max()),
                ymin=float(world_pts[:, 1].min()),
                ymax=float(world_pts[:, 1].max()),
                zmin=float(world_pts[:, 2].min()),
                zmax=float(world_pts[:, 2].max()),
            ),
        )

        model = CanonicalModel(
            schema_version="0.5.0",
            source=_make_source_metadata(),
            elements=[element],
            model_bounds=BoundingBox(
                xmin=element.bounding_box.xmin,
                xmax=element.bounding_box.xmax,
                ymin=element.bounding_box.ymin,
                ymax=element.bounding_box.ymax,
                zmin=element.bounding_box.zmin,
                zmax=element.bounding_box.zmax,
            ),
        )

        rebased_model, rebase_vec = rebase_model_to_origin(model, auto_rebase=True)
        assert rebase_vec[0] < -500000.0, f"Expected negative rebase, got {rebase_vec[0]}"
        assert rebase_vec[1] < -1000000.0, f"Expected negative rebase, got {rebase_vec[1]}"

        rebased_elem = rebased_model.elements[0]
        rebased_vertices = np.array(rebased_elem.mesh.vertices)
        M_rebased = np.array(rebased_elem.placement["effective_world"]).reshape(4, 4)

        # Verification: local transformed by placement matrix equals rebased vertex within 10^-9 m
        rebased_prov = (M_rebased @ homo_local.T).T[:, :3]
        max_err = np.max(np.abs(rebased_prov - rebased_vertices))
        assert max_err <= 1e-9, f"Massive negative provenance drift {max_err:.2e} m > 1e-9 m"

    def test_sub_millimeter_offsets_and_rebase_thresholds(self):
        """Stress-test sub-millimeter offsets and rebase activation thresholds."""
        # 0.5 mm = 5e-4 m, 0.2 mm = 2e-4 m, -0.1 mm = -1e-4 m
        sub_mm_shift = [0.0005, 0.0002, -0.0001]
        local_pts = np.array([[1.0, 2.0, 3.0]], dtype=np.float64)
        M_world = _create_affine_matrix(translation=[10.0, 20.0, 30.0])

        homo_local = np.hstack([local_pts, np.ones((1, 1))])
        world_pts = (M_world @ homo_local.T).T[:, :3]

        element = CanonicalElement(
            step_id=303,
            global_id="GLOBAL_SUB_MM_03",
            ifc_type="IfcBeam",
            mesh=TriangleMesh(vertices=world_pts.tolist(), faces=[[0, 0, 0]]),
            placement=dict(
                status="CONFIRMED",
                effective_world=M_world.ravel().tolist(),
            ),
        )
        model = CanonicalModel(
            schema_version="0.5.0",
            source=_make_source_metadata(),
            elements=[element],
        )

        # Explicit sub-millimeter rebase vector
        rebased_model, rebase_vec = rebase_model_to_origin(
            model, rebase_vector=sub_mm_shift, auto_rebase=False
        )
        assert rebase_vec == (0.0005, 0.0002, -0.0001)

        rebased_elem = rebased_model.elements[0]
        rebased_vertices = np.array(rebased_elem.mesh.vertices)
        M_rebased = np.array(rebased_elem.placement["effective_world"]).reshape(4, 4)

        rebased_prov = (M_rebased @ homo_local.T).T[:, :3]
        max_err = np.max(np.abs(rebased_prov - rebased_vertices))
        assert max_err <= 1e-9, f"Sub-millimeter provenance drift {max_err:.2e} m > 1e-9 m"

        # Threshold test: shift exactly at 1e-6 m boundary
        model_sub = CanonicalModel(
            schema_version="0.5.0",
            source=_make_source_metadata(),
            elements=[element],
        )
        _, vec_sub = rebase_model_to_origin(model_sub, rebase_vector=[1e-6, 1e-6, 1e-6])
        # Since abs(x) > 1e-6 is false for 1e-6, it should be a no-op (0, 0, 0)
        assert vec_sub == (0.0, 0.0, 0.0)

        # Shift slightly above threshold: 1.01e-6 m
        model_above = CanonicalModel(
            schema_version="0.5.0",
            source=_make_source_metadata(),
            elements=[element],
        )
        _, vec_above = rebase_model_to_origin(model_above, rebase_vector=[1.01e-6, 0.0, 0.0])
        assert vec_above == (1.01e-6, 0.0, 0.0)

    def test_matrix_representation_polymorphism_and_openings_hierarchy(self):
        """Stress-test all matrix storage formats (1D, 2D, ndarray) and opening/port hierarchy."""
        dx, dy, dz = 1500.0, -2500.0, 30.0

        M_4x4 = _create_affine_matrix(
            translation=[1500.0, -2500.0, 30.0],
            rotation_deg=(45.0, 0.0, 0.0),
        )
        mat_1d_list = M_4x4.ravel().tolist()
        mat_2d_list = M_4x4.tolist()
        mat_1d_arr = M_4x4.ravel()
        mat_2d_arr = M_4x4.copy()

        # Direct test on _translate_matrix_4x4 for all 4 types
        res_1d = _translate_matrix_4x4(mat_1d_list, dx, dy, dz)
        assert isinstance(res_1d, list) and len(res_1d) == 16
        assert np.allclose(np.array(res_1d).reshape(4, 4)[:3, 3], [0.0, 0.0, 0.0], atol=1e-9)

        res_2d = _translate_matrix_4x4(mat_2d_list, dx, dy, dz)
        assert isinstance(res_2d, list) and len(res_2d) == 4 and len(res_2d[0]) == 4
        assert np.allclose(np.array(res_2d)[:3, 3], [0.0, 0.0, 0.0], atol=1e-9)

        res_arr1 = _translate_matrix_4x4(mat_1d_arr, dx, dy, dz)
        assert isinstance(res_arr1, np.ndarray) and res_arr1.shape == (16,)
        assert np.allclose(res_arr1.reshape(4, 4)[:3, 3], [0.0, 0.0, 0.0], atol=1e-9)

        res_arr2 = _translate_matrix_4x4(mat_2d_arr, dx, dy, dz)
        assert isinstance(res_arr2, np.ndarray) and res_arr2.shape == (4, 4)
        assert np.allclose(res_arr2[:3, 3], [0.0, 0.0, 0.0], atol=1e-9)

        # Hierarchy test: openings and ports
        opening_pts = np.array([[1501.0, -2499.0, 31.0]])
        port_pos = [1502.0, -2498.0, 32.0]

        element = CanonicalElement(
            step_id=404,
            global_id="GLOBAL_HIERARCHY_04",
            ifc_type="IfcWall",
            mesh=TriangleMesh(vertices=[[1500.0, -2500.0, 30.0]], faces=[[0, 0, 0]]),
            placement=dict(effective_world=mat_2d_list),
            openings=[
                OpeningReference(
                    opening_global_id="OPENING_01",
                    opening_step_id=901,
                    opening_name="Opening 01",
                    mesh=TriangleMesh(vertices=opening_pts.tolist(), faces=[[0, 0, 0]]),
                    placement=dict(effective_world=mat_1d_arr),
                    bounding_box=BoundingBox(xmin=1501.0, xmax=1502.0, ymin=-2499.0, ymax=-2498.0, zmin=31.0, zmax=32.0),
                )
            ],
            ports=[PortReference(port_global_id="PORT_01", port_step_id=902, world_position=port_pos)],
        )
        source_meta = _make_source_metadata()
        model = CanonicalModel(
            schema_version="0.5.0",
            elements=[element],
            source=source_meta,
            sources=[source_meta],
        )

        rebased_model, _ = rebase_model_to_origin(model, rebase_vector=[dx, dy, dz])
        elem_reb = rebased_model.elements[0]

        # Opening vertex check
        assert np.allclose(elem_reb.openings[0].mesh.vertices[0], [1.0, 1.0, 1.0], atol=1e-9)
        # Opening placement check
        op_mat = np.array(elem_reb.openings[0].placement["effective_world"]).reshape(4, 4)
        assert np.allclose(op_mat[:3, 3], [0.0, 0.0, 0.0], atol=1e-9)
        # Port position check
        assert np.allclose(elem_reb.ports[0].world_position, [2.0, 2.0, 2.0], atol=1e-9)
        # Model source rebase vector metadata recorded
        assert model.source.rebase_vector == [dx, dy, dz]
        assert model.sources[0].rebase_vector == [dx, dy, dz]

    def test_rebase_vector_validation_adversarial_inputs(self):
        """Stress-test adversarial inputs to rebase_model_to_origin."""
        model = CanonicalModel(schema_version="0.5.0", source=_make_source_metadata())

        # Wrong dimensions
        with pytest.raises(ValueError, match="rebase_vector must be"):
            rebase_model_to_origin(model, rebase_vector=[1.0, 2.0])
        with pytest.raises(ValueError, match="rebase_vector must be"):
            rebase_model_to_origin(model, rebase_vector=[1.0, 2.0, 3.0, 4.0])

        # Non-finite values
        with pytest.raises(ValueError, match="rebase_vector must be"):
            rebase_model_to_origin(model, rebase_vector=[float("nan"), 0.0, 0.0])
        with pytest.raises(ValueError, match="rebase_vector must be"):
            rebase_model_to_origin(model, rebase_vector=[0.0, float("inf"), 0.0])

        # Booleans
        with pytest.raises(ValueError, match="rebase_vector must be"):
            rebase_model_to_origin(model, rebase_vector=[True, 1.0, 2.0])

        # Types
        with pytest.raises(ValueError, match="rebase_vector must be"):
            rebase_model_to_origin(model, rebase_vector="invalid")


# ===========================================================================
# 2. EMPIRICAL CHALLENGES: ADAPTIVE CAD TOLERANCE STRESS
# ===========================================================================


class TestAdaptiveCADToleranceStress:
    """Rigorous empirical stress testing of adaptive CAD welding, manifolds, and volume preservation."""

    def test_cad_micro_gaps_welded_into_closed_manifold(self):
        """Feed micro-gaps (10^-7 to 10^-6 m).

        Verify that:
        1. Strict mode (1e-12 m) REFUSES the mesh with SOURCE_SURFACE_REMAINS_OPEN.
        2. Adaptive CAD mode (1e-6 m) WELDS micro-gaps into closed manifold.
        3. Volume preservation > 99.9% is satisfied.
        """
        for gap in [1e-7, 5e-7, 1e-6]:
            cube = _build_cube_mesh(size=(1.0, 1.0, 1.0))
            raw_vol = _compute_mesh_volume(np.array(cube.vertices), np.array(cube.faces))
            assert abs(raw_vol - 1.0) < 1e-6

            # Duplicate vertex 1 and introduce a micro-gap on one face
            cube.vertices.append([1.0 + gap, 0.0, 0.0])
            new_idx = len(cube.vertices) - 1
            # Replace vertex 1 in face [0, 1, 5] with new_idx
            cube.faces[4] = [0, new_idx, 5]

            # Quality check: raw mesh now has open edges due to micro-gap
            raw_qual = inspect_mesh_quality(cube)
            assert raw_qual["open_edges"] > 0, f"Expected open edges for gap {gap}"

            # 1. Strict mode MUST REFUSE
            _, strict_proof = normalize_source_mesh(cube, adaptive_cad=False)
            assert strict_proof["status"] == "REFUSED"
            assert strict_proof["reason"] == "SOURCE_SURFACE_REMAINS_OPEN"

            # 2. Adaptive CAD mode MUST NORMALIZE
            cand, cad_proof = normalize_source_mesh(cube, adaptive_cad=True, cad_tolerance=1e-6)
            assert cad_proof["status"] == "NORMALIZED", (
                f"Failed for gap {gap}: {cad_proof.get('reason')}"
            )
            assert bool(cad_proof["result_quality"]["is_closed_manifold"]) is True
            assert cad_proof["result_quality"]["open_edges"] == 0
            assert cad_proof["vertices_merged"] >= 1
            assert cad_proof["max_vertex_displacement_m"] <= 1e-6

            # 3. Volume preservation > 99.9%
            cand_vol = _compute_mesh_volume(np.array(cand.vertices), np.array(cand.faces))
            vol_ratio = cand_vol / raw_vol
            assert vol_ratio >= 0.999, f"Volume ratio violated: {vol_ratio}"
            assert abs(cand_vol - 1.0) < 1e-4

    def test_large_architectural_gaps_remain_open_and_refused(self):
        """Feed large gaps (10^-3 m / 1 mm and 2 mm).

        Verify that:
        1. Large gaps are NEVER falsely welded into closed manifolds.
        2. Status is REFUSED with SOURCE_SURFACE_REMAINS_OPEN.
        3. Mesh vertices and faces are left completely untouched.
        """
        for gap in [1e-3, 2e-3, 5e-3]:
            cube = _build_cube_mesh(size=(1.0, 1.0, 1.0))
            # Create an opening along vertex 1
            cube.vertices.append([1.0 + gap, 0.0, 0.0])
            cube.faces[4] = [0, len(cube.vertices) - 1, 5]

            cand, proof = normalize_source_mesh(
                cube, adaptive_cad=True, cad_tolerance=CAD_TOLERANCE_M, max_tolerance=MAX_CAD_DISPLACEMENT_M
            )
            assert proof["status"] == "REFUSED"
            assert proof["reason"] == "SOURCE_SURFACE_REMAINS_OPEN"
            assert proof["candidate_quality"]["open_edges"] > 0
            # Input mesh untouched
            assert len(cand.vertices) == len(cube.vertices)
            assert cand.faces == cube.faces

    def test_non_manifold_meshes_rejected(self):
        """Feed non-manifold meshes (T-junctions, 3 faces sharing one edge).

        Verify that non-manifold topologies are rejected safely without corrupting data.
        """
        cube = _build_cube_mesh(size=(1.0, 1.0, 1.0))
        # Add a 13th triangle sharing edge (0, 1) to create a non-manifold T-junction edge
        cube.vertices.append([0.5, -0.5, 0.0])
        extra_idx = len(cube.vertices) - 1
        cube.faces.append([0, 1, extra_idx])

        # Mesh quality check confirms non-manifold edge
        qual = inspect_mesh_quality(cube)
        assert qual["non_manifold_edges"] > 0

        _, proof = normalize_source_mesh(cube, adaptive_cad=True)
        assert proof["status"] == "REFUSED"
        assert proof["reason"] == "NON_MANIFOLD_SOURCE_EDGES"

    def test_sliver_triangles_and_collapsing_edges_safety(self):
        """Stress-test sliver triangles.

        1. A sliver triangle where 2 vertices are closer than CAD tolerance (< 10^-6 m):
           Welding collapses 2 vertices of the triangle into 1, yielding degenerate triangle [0, 0, 2].
           Verify engine REFUSES with WELD_WOULD_COLLAPSE_OR_INVALIDATE_TRIANGLES.
        2. A collinear degenerate triangle in raw input:
           Verify engine REFUSES with INVALID_OR_DEGENERATE_SOURCE_TRIANGLES.
        """
        # 1. Edge collapse under welding:
        # Create a cube, and add a sliver triangle [0, v_sliver, 1] where v_sliver is 1e-7 m from 0.
        # But wait! If we add an extra face to a closed cube, it would make edge (0, 1) non-manifold.
        # Instead, replace one of the cube's faces [0, 2, 1] with [0, 2, v_sliver], and add [v_sliver, 2, 1].
        # Distance between 0 and v_sliver is 1e-7 m (< 1e-6 m tolerance).
        cube = _build_cube_mesh()
        v_sliver = [cube.vertices[0][0] + 1e-7, cube.vertices[0][1], cube.vertices[0][2]]
        cube.vertices.append(v_sliver)
        sliver_idx = len(cube.vertices) - 1
        cube.faces[0] = [0, 2, sliver_idx]
        cube.faces.append([sliver_idx, 2, 1])

        # Quality check: raw faces are valid triangles (no duplicate vertex indices)
        raw_qual = inspect_mesh_quality(cube)
        assert not raw_qual["degenerate_faces"]

        # When welded with tolerance 1e-6 m, vertex 0 and sliver_idx merge into one!
        # Face [0, 2, sliver_idx] becomes [0, 2, 0] -> degenerate face!
        _, proof = normalize_source_mesh(cube, adaptive_cad=True, cad_tolerance=1e-6)
        assert proof["status"] == "REFUSED"
        assert proof["reason"] == "WELD_WOULD_COLLAPSE_OR_INVALIDATE_TRIANGLES"

        # 2. Raw collinear degenerate triangle (e.g. vertices 0, 1, and midpoint)
        cube_collinear = _build_cube_mesh()
        cube_collinear.faces[0] = [0, 0, 1]  # duplicate vertex index

        _, proof_collinear = normalize_source_mesh(cube_collinear, adaptive_cad=True)
        assert proof_collinear["status"] == "REFUSED"
        assert proof_collinear["reason"] == "INVALID_OR_DEGENERATE_SOURCE_TRIANGLES"

    def test_volume_preservation_boundary_violation(self):
        """Stress-test volume preservation safety gate.

        Construct a thin plate where welding a micro-gap alters volume by > 0.1% (< 99.9% preserved).
        Verify that engine REFUSES with VOLUME_PRESERVATION_VIOLATED.
        """
        # Thin plate: 1m x 1m x 0.0001m (thickness = 100 micrometers, volume = 1e-4 m^3)
        plate = _build_cube_mesh(size=(1.0, 1.0, 0.0001))
        raw_vol = _compute_mesh_volume(np.array(plate.vertices), np.array(plate.faces))
        assert abs(raw_vol - 1e-4) < 1e-7

        # Split vertex 4 (top corner) by shifting it 2 um along Z (thickness change ~2% locally)
        # Shift creates a gap of 2 um (2e-6 m)
        plate.vertices.append([plate.vertices[4][0], plate.vertices[4][1], plate.vertices[4][2] - 5e-6])
        new_idx = len(plate.vertices) - 1
        plate.faces[2] = [new_idx, 5, 6]  # Top face now uses lower vertex

        # Weld with tolerance 6e-6 m.
        # But notice: _compute_mesh_volume calculates volume of raw vs candidate.
        # Let's verify volume ratio check logic directly
        # When thickness is 100 um, shifting by 5 um changes local volume by ~5%!
        _, proof = normalize_source_mesh(
            plate,
            adaptive_cad=True,
            cad_tolerance=6e-6,
            max_tolerance=1e-5,
            min_volume_ratio=0.999,
        )
        # Should be refused because volume change exceeds 0.1%
        assert proof["status"] == "REFUSED"
        assert proof["reason"] == "VOLUME_PRESERVATION_VIOLATED"
        assert (proof["volume_ratio"] < 0.999 or proof["volume_ratio"] > 1.001)

    def test_normalize_element_geometry_canonical_element_lifecycle(self):
        """Test normalize_element_geometry integration with CanonicalElement and GeometryStatus."""
        cube = _build_cube_mesh(size=(2.0, 2.0, 2.0))
        # Micro gap of 5e-7 m
        cube.vertices.append([2.0 + 5e-7, 0.0, 0.0])
        cube.faces[4] = [0, len(cube.vertices) - 1, 5]

        element = CanonicalElement(
            step_id=505,
            global_id="GLOBAL_WALL_05",
            ifc_type="IfcWall",
            mesh=cube,
            geometry_status=GeometryStatus.NOT_PROCESSED,
        )

        res_elem, proof = normalize_element_geometry(element, cad_tolerance=1e-6)
        assert proof["status"] == "NORMALIZED"
        assert res_elem.geometry_status == GeometryStatus.VALID
        assert res_elem.mesh.is_closed_manifold is True

        # Now test an unhealable mesh on CanonicalElement
        unhealable_cube = _build_cube_mesh(size=(2.0, 2.0, 2.0))
        unhealable_cube.vertices.append([2.0 + 0.05, 0.0, 0.0])  # 5cm gap
        unhealable_cube.faces[4] = [0, len(unhealable_cube.vertices) - 1, 5]

        element_unhealable = CanonicalElement(
            step_id=506,
            global_id="GLOBAL_WALL_06",
            ifc_type="IfcWall",
            mesh=unhealable_cube,
            geometry_status=GeometryStatus.NOT_PROCESSED,
        )
        res_fail, proof_fail = normalize_element_geometry(element_unhealable, cad_tolerance=1e-6)
        assert proof_fail["status"] == "REFUSED"
        assert res_fail.geometry_status == GeometryStatus.NOT_PROCESSED  # Not promoted to VALID


# ===========================================================================
# 3. EMPIRICAL CHALLENGES: SQLITE WAL PERSISTENCE & CONCURRENCY
# ===========================================================================


class TestSQLiteDurabilityStress:
    """Stress testing of SQLite WAL configuration, crash recovery, and thread concurrency."""

    def test_sqlite_wal_pragmas_on_every_connection(self, tmp_path):
        """WP-P1-03: SQLite WAL, busy_timeout >= 10 s, and synchronous per IFCFDS_ENV configured."""
        repo = JobRepository(root=tmp_path)
        with repo._get_connection() as conn:
            journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0].upper()
            busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
            sync_mode = conn.execute("PRAGMA synchronous;").fetchone()[0]

            assert journal_mode == "WAL"
            # Real repository connects with timeout=30 s (stronger than the removed copy's 10 s).
            assert busy_timeout >= 10000
            # NORMAL (1) in local/test; FULL (2) is covered by tests/test_sqlite_production_sync.py.
            assert sync_mode in (1, "NORMAL")

    def test_reconcile_orphaned_jobs_recovers_crashed_workers(self, tmp_path):
        """Startup reconciliation (real JobService path): crashed RUNNING job -> FAILED with diagnostics."""
        from ifc_to_fds.adapters.jobs.service import JobService

        repo = JobRepository(root=tmp_path)

        # 1. Seed simulated stuck RUNNING job (worker crashed abruptly)
        job1_dir = tmp_path / "job-orphaned-1"
        job1_dir.mkdir(parents=True, exist_ok=True)
        (job1_dir / "progress.json").write_text(json.dumps({"stage": "GEOMETRY_EXTRACTION"}), encoding="utf-8")

        repo.set("job-orphaned-1", {
            "id": "job-orphaned-1",
            "state": "RUNNING",
            "directory": str(job1_dir),
            "created": time.time() - 300,
            "started": time.time() - 250,
            "mode": "convert",
        })

        # 2. Seed a completed job that should not be touched
        comp_dir = tmp_path / "job-completed"
        comp_dir.mkdir(parents=True, exist_ok=True)
        (comp_dir / "result.json").write_text(json.dumps({"status": "MAPPING_VERIFIED", "artifacts": {}}), encoding="utf-8")

        repo.set("job-completed", {
            "id": "job-completed",
            "state": "COMPLETED",
            "directory": str(comp_dir),
            "created": time.time() - 500,
            "finished": time.time() - 400,
            "mode": "convert",
        })

        # 3. Boot the real service on the same root: this runs _reconcile_startup_jobs
        service = JobService(root=tmp_path)
        try:
            reconciled_job = service.repository.get("job-orphaned-1")
            assert reconciled_job is not None
            assert reconciled_job["state"] == "FAILED"
            assert "terminated unexpectedly" in reconciled_job["error"]
            assert service.repository.get("job-completed")["state"] == "COMPLETED"
        finally:
            service.close()

        # Check diagnostic file creation on disk
        diag_file = job1_dir / "diagnostics.json"
        assert diag_file.is_file()
        diag_data = json.loads(diag_file.read_text(encoding="utf-8"))
        assert diag_data["name"] == "AbortError"
        assert diag_data["jobId"] == "job-orphaned-1"
        assert diag_data["stage"] == "GEOMETRY_EXTRACTION"
        assert "terminated unexpectedly" in diag_data["message"]

        # 4. Verify SQLite WAL persistence: simulate new server instance booting on the same DB
        repo_restarted = JobRepository(root=tmp_path)
        persisted_job = repo_restarted.get("job-orphaned-1")
        assert persisted_job is not None
        assert persisted_job["state"] == "FAILED"
        assert "terminated unexpectedly" in persisted_job["error"]

        completed_job = repo_restarted.get("job-completed")
        assert completed_job is not None
        assert completed_job["state"] == "COMPLETED"

    def test_sqlite_concurrent_multithreaded_read_write_stress(self, tmp_path):
        """Stress-test concurrent multi-threaded execution (8 threads, 120 jobs).

        Verify zero database locked errors and complete consistency under load.
        """
        repo = JobRepository(root=tmp_path)
        errors = []

        def worker_thread(tid: int):
            try:
                for i in range(15):
                    jid = f"stress-job-{tid}-{i}"
                    jdir = tmp_path / jid
                    jdir.mkdir(parents=True, exist_ok=True)
                    repo.set(jid, {
                        "id": jid,
                        "state": "RUNNING",
                        "directory": str(jdir),
                        "created": time.time(),
                        "started": time.time(),
                    })
                    # Read snapshot
                    repo.snapshot(jid)
                    # Update
                    j = repo.get(jid)
                    if j:
                        j["state"] = "COMPLETED"
                        j["finished"] = time.time()
                        repo.set(jid, j)
            except Exception as exc:
                errors.append((tid, exc))

        threads = [threading.Thread(target=worker_thread, args=(t,)) for t in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent operations threw errors: {errors}"
        assert len(repo.all_jobs()) == 8 * 15
