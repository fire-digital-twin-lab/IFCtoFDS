"""Empirical adversarial stress test harness for Milestone 3 (P0 Implementation).

Orchestrated by Challenger 1 (critic/specialist).
Empirically tests:
1. FDS exporter output: valid syntax, &SURF ID='HVAC' existence, no surface clashes, NIST FDS solver validation.
2. Stress-testing safe_unit_normals & compute_face_normals on degenerate triangles, collinear points, coincident vertices, inverted windings, huge coordinates, extreme floats (NaNs/Infs).
3. measure_architecture_baseline.py verification: execution, data integrity, edge cases.
"""

import json
import os
from pathlib import Path
import runpy
import warnings
import numpy as np
import pytest

from ifc_to_fds.core.canonical import BoundingBox, CanonicalModel, TriangleMesh
from ifc_to_fds.domain.source.model import SourceMetadata
from ifc_to_fds.domain.scope.model import ScopeDecision
from ifc_to_fds.domain.validation import AuditConfig
from ifc_to_fds.geometry.mesh import (
    compute_face_normals,
    safe_unit_normals,
)
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.pipeline import prepare
from ifc_to_fds.validation.parser import parse_fds
from ifc_to_fds.validation.solver import solver_gates


FDS_SOLVER_PATH = r"D:\Users\Documents\HUCE\NCKH PCCC\IFCtoFDS\.deps\fds-6.11.1\firemodels\FDS6\bin\fds_openmp.exe"


# ===========================================================================
# 1. EMPIRICAL CHALLENGES: FDS EXPORTER OUTPUT & SURFACE CLASH
# ===========================================================================


class TestFDSExporterEmpirical:
    """Empirically tests FDS deck generation, surface collision, and NIST solver acceptance."""

    def test_fds_export_without_hvac_syntax_and_solver(self, tmp_path):
        """Verify FDS deck without HVAC contains SURF HVAC, has unique SURF IDs, and FDS solver accepts it."""
        source = SourceMetadata(
            filename="no_hvac.ifc",
            file_path="no_hvac.ifc",
            file_hash_sha256="1" * 64,
            file_size_bytes=200,
            schema_version="IFC4",
        )
        model = CanonicalModel(
            schema_version="0.5.0",
            source=source,
            simulation_domain=BoundingBox(xmin=0, xmax=6, ymin=0, ymax=6, zmin=0, zmax=3),
        )
        plan_mapping(model)
        text, manifest = serialize_fds(model)

        # 1. Parse using IFCtoFDS parser
        parsed = parse_fds(text)
        assert len(parsed.errors) == 0, f"Parser errors: {parsed.errors}"

        # 2. Verify all emitted &SURF IDs are unique
        surf_records = [r for r in parsed.records if r.kind == "SURF"]
        surf_ids = [r.values.get("ID", [None])[0] for r in surf_records if "ID" in r.values]
        assert len(surf_ids) == len(set(surf_ids)), f"Duplicate SURF IDs found: {surf_ids}"
        assert "HVAC" in surf_ids
        assert "CONCRETE" in surf_ids
        assert "GLASS" in surf_ids
        assert "STEEL" in surf_ids
        assert "WOOD" in surf_ids

        # 3. Ensure HVAC has DEFAULT=False so it doesn't accidentally become default
        hvac_record = next(r for r in surf_records if r.values.get("ID") == ["HVAC"])
        assert hvac_record.values.get("DEFAULT") == [False]

        # 4. Run real NIST FDS solver via solver_gates to verify no syntax errors or undefined surface errors
        if os.path.isfile(FDS_SOLVER_PATH):
            config = AuditConfig(
                solver_executable=FDS_SOLVER_PATH,
                solver_evidence_directory=str(tmp_path / "solver_ev_no_hvac"),
                solver_timeout_s=30,
            )
            gate, evidence = solver_gates(text, config)
            assert gate.status == "PASS", f"Solver gate failed: {gate.model_dump()}\nEvidence: {evidence}"

    def test_fds_export_with_hvac_network_syntax_and_solver(self, tmp_path):
        """Verify FDS deck with operational HVAC network points to &SURF ID='HVAC' and FDS solver accepts it."""
        factory = runpy.run_path(
            str(Path(__file__).parents[1] / "scripts/audit-project-logic.py")
        )["make_connected_duct_fixture"]
        path = tmp_path / "ducts_challenger.ifc"
        factory(path)

        config = {
            "simulation_domain": dict(xmin=0, xmax=10, ymin=0, ymax=5, zmin=0, zmax=5),
        }
        model = prepare([str(path)], config)
        model.simulation_domain.xmin = 1.0
        for e in model.elements:
            if e.ifc_type == "IfcWall":
                e.scope_decision = ScopeDecision.OUT_OF_SCOPE

        ducts = [e for e in model.elements if e.ifc_type == "IfcDuctSegment"]
        decisions = {}
        for duct in ducts:
            endpoints = {}
            for p in duct.ports:
                if p.world_position[0] == 1.0:
                    endpoints[p.port_key] = {"kind": "VENT", "vent_xb": [1.0, 1.0, 1.0, 1.4, 2.0, 2.3]}
                elif p.world_position[0] == 7.0:
                    endpoints[p.port_key] = {"kind": "AMBIENT"}
            decisions[duct.entity_key] = dict(
                action="HVAC",
                policy_version="hvac-v1",
                reviewer="challenger",
                rationale="Challenger test vent endpoint emission",
                evidence="IFC port",
                hvac=dict(area_m2=0.12, perimeter_m=1.4, endpoints=endpoints),
            )

        plan_mapping(model, decisions=decisions)
        text, manifest = serialize_fds(model)

        # 1. Parse with IFCtoFDS parser
        parsed = parse_fds(text)
        assert len(parsed.errors) == 0, f"Parser errors: {parsed.errors}"

        # 2. Check VENT records referencing HVAC
        vent_records = [r for r in parsed.operational_records if r.kind == "VENT"]
        assert len(vent_records) > 0, "No operational VENT records generated!"
        for v in vent_records:
            surf_id = v.values.get("SURF_ID", [None])[0]
            assert surf_id == "HVAC", f"Expected SURF_ID='HVAC', got {surf_id}"

        # 3. Check uniqueness of all SURF IDs
        surf_records = [r for r in parsed.records if r.kind == "SURF"]
        surf_ids = [r.values.get("ID", [None])[0] for r in surf_records if "ID" in r.values]
        assert len(surf_ids) == len(set(surf_ids)), f"Duplicate SURF IDs: {surf_ids}"

        # 4. Real NIST FDS execution test via solver_gates
        if os.path.isfile(FDS_SOLVER_PATH):
            audit_config = AuditConfig(
                solver_executable=FDS_SOLVER_PATH,
                solver_evidence_directory=str(tmp_path / "solver_ev_hvac"),
                solver_timeout_s=30,
            )
            gate, evidence = solver_gates(text, audit_config)
            assert gate.status == "PASS", f"Solver gate failed: {gate.model_dump()}\nEvidence: {evidence}"


# ===========================================================================
# 2. EMPIRICAL CHALLENGES: MESH NORMALS STRESS TEST
# ===========================================================================


class TestMeshNormalsStress:
    """Stress-tests safe_unit_normals and compute_face_normals under adversarial degenerate conditions."""

    def test_safe_unit_normals_coincident_and_zero_vectors(self):
        """Test with exactly zero vectors and sub-epsilon vectors."""
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")

            # 1D zero vector
            n1 = safe_unit_normals([0.0, 0.0, 0.0])
            assert np.array_equal(n1, [0.0, 0.0, 1.0])
            assert np.isfinite(n1).all()

            # 2D batch of zeros
            zeros = np.zeros((100, 3), dtype=np.float64)
            n_zeros = safe_unit_normals(zeros)
            assert n_zeros.shape == (100, 3)
            assert np.allclose(n_zeros, [0.0, 0.0, 1.0])
            assert np.isfinite(n_zeros).all()

            # Sub-epsilon vectors (below default eps 1e-14)
            sub_eps = np.array([
                [1e-15, 0.0, 0.0],
                [0.0, 1e-15, 0.0],
                [0.0, 0.0, 1e-15],
                [1e-20, 1e-20, 1e-20],
                [1e-300, 0.0, 0.0],
            ])
            n_sub = safe_unit_normals(sub_eps)
            assert np.allclose(n_sub, [0.0, 0.0, 1.0])
            assert np.isfinite(n_sub).all()

        runtime_warnings = [w for w in recorded if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0, f"Unexpected runtime warnings: {[str(w.message) for w in runtime_warnings]}"

    def test_safe_unit_normals_huge_and_overflow_vectors(self):
        """Test with huge coordinates, GIS coordinates, and float overflow/underflow."""
        # 1. GIS / UTM scale vectors (e.g. 500_000m)
        gis_vec = np.array([500_000.0, 2_300_000.0, 50.0])
        n_gis = safe_unit_normals(gis_vec)
        expected = gis_vec / np.linalg.norm(gis_vec)
        assert np.allclose(n_gis, expected)
        assert np.isclose(np.linalg.norm(n_gis), 1.0)
        assert np.isfinite(n_gis).all()

        # 2. Large finite coordinates up to 1e150 (within float64 range without norm overflow)
        large_vec = np.array([1e150, 0.0, 0.0])
        n_large = safe_unit_normals(large_vec)
        assert np.allclose(n_large, [1.0, 0.0, 0.0])
        assert np.isfinite(n_large).all()

        # 3. Extreme vectors that exceed float64 dynamic range (1e250)
        # Even if np.linalg.norm overflows to inf, safe_unit_normals MUST return finite numbers (no NaN/Inf)
        overflow_vec = np.array([1e250, 1e250, 0.0])
        n_overflow = safe_unit_normals(overflow_vec)
        assert np.isfinite(n_overflow).all(), f"Expected finite normal, got {n_overflow}"
        assert np.allclose(n_overflow, [0.0, 0.0, 1.0])

        # 4. Vectors containing Infs or NaNs
        nan_vec = np.array([[np.nan, 1.0, 0.0], [np.inf, 0.0, 0.0], [-np.inf, 2.0, 3.0]])
        n_nan = safe_unit_normals(nan_vec)
        assert n_nan.shape == (3, 3)
        assert np.isfinite(n_nan).all(), f"Expected finite normals for NaN/Inf inputs, got {n_nan}"
        assert np.allclose(n_nan, [0.0, 0.0, 1.0])

    def test_compute_face_normals_collinear_and_coincident_triangles(self):
        """Test compute_face_normals on meshes with coincident vertices and collinear points."""
        mesh = TriangleMesh(
            vertices=[
                # Coincident triplet (3 points at origin)
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                # 2 coincident vertices + 1 distinct
                [1.0, 1.0, 1.0],
                [1.0, 1.0, 1.0],
                [2.0, 2.0, 2.0],
                # Collinear along X axis
                [10.0, 0.0, 0.0],
                [20.0, 0.0, 0.0],
                [30.0, 0.0, 0.0],
                # Collinear along diagonal
                [0.0, 0.0, 0.0],
                [5.0, 5.0, 5.0],
                [10.0, 10.0, 10.0],
                # Valid counter-clockwise triangle in XY plane (normal +Z)
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                # Inverted winding (clockwise triangle in XY plane, normal -Z)
                [0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [1.0, 0.0, 0.0],
            ],
            faces=[
                [0, 1, 2],    # 3 coincident
                [3, 4, 5],    # 2 coincident
                [6, 7, 8],    # Collinear X
                [9, 10, 11],  # Collinear diagonal
                [12, 13, 14], # Valid CCW (+Z)
                [15, 16, 17], # Inverted CW (-Z)
            ],
        )

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")

            normals = compute_face_normals(mesh)
            assert normals.shape == (6, 3)
            assert np.isfinite(normals).all()

            # All degenerate faces must yield finite default [0, 0, 1]
            assert np.allclose(normals[0], [0.0, 0.0, 1.0])
            assert np.allclose(normals[1], [0.0, 0.0, 1.0])
            assert np.allclose(normals[2], [0.0, 0.0, 1.0])
            assert np.allclose(normals[3], [0.0, 0.0, 1.0])

            # Valid CCW face normal = +Z
            assert np.allclose(normals[4], [0.0, 0.0, 1.0])

            # Inverted CW face normal = -Z
            assert np.allclose(normals[5], [0.0, 0.0, -1.0])

        runtime_warnings = [w for w in recorded if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0, f"Unexpected runtime warnings: {[str(w.message) for w in runtime_warnings]}"

    def test_compute_face_normals_needle_and_huge_coordinates(self):
        """Test compute_face_normals on needle/sliver triangles and extreme coordinates."""
        # Needle triangle: base 1000m, height 1e-18m -> cross product < 1e-14 -> degenerate
        needle_mesh = TriangleMesh(
            vertices=[
                [0.0, 0.0, 0.0],
                [1000.0, 0.0, 0.0],
                [500.0, 1e-18, 0.0],
            ],
            faces=[[0, 1, 2]],
        )
        normals = compute_face_normals(needle_mesh)
        assert np.isfinite(normals).all()
        assert np.allclose(normals[0], [0.0, 0.0, 1.0])

        # Huge coordinate triangle: vertices at 1e12
        huge_mesh = TriangleMesh(
            vertices=[
                [1e12, 1e12, 0.0],
                [1e12 + 10.0, 1e12, 0.0],
                [1e12, 1e12 + 10.0, 0.0],
            ],
            faces=[[0, 1, 2]],
        )
        normals_huge = compute_face_normals(huge_mesh)
        assert np.isfinite(normals_huge).all()
        # Normal should still point along +Z
        assert np.allclose(normals_huge[0], [0.0, 0.0, 1.0])

    def test_compute_face_normals_empty_mesh_and_boundary_cases(self):
        """Test compute_face_normals on empty meshes or meshes with non-standard face arrays."""
        # Empty mesh (0 faces)
        empty_mesh = TriangleMesh(vertices=[], faces=[])
        normals_empty = compute_face_normals(empty_mesh)
        assert normals_empty.shape == (0, 3)

        # Mesh with faces but 0 vertices
        dummy_mesh = type("Dummy", (), {"vertices": [], "faces": [[0, 1, 2], [1, 2, 3]]})()
        normals_dummy = compute_face_normals(dummy_mesh)
        assert normals_dummy.shape == (2, 3)
        assert np.allclose(normals_dummy, [0.0, 0.0, 1.0])

        # Invalid vector shape to safe_unit_normals should raise ValueError cleanly
        with pytest.raises(ValueError, match="Expected 3D vectors"):
            safe_unit_normals([1.0, 2.0])

        with pytest.raises(ValueError, match="Expected 3D vectors"):
            safe_unit_normals(np.ones((5, 4)))


# ===========================================================================
# 3. EMPIRICAL CHALLENGES: MEASURE ARCHITECTURE BASELINE SCRIPT
# ===========================================================================


class TestMeasureArchitectureBaselineEmpirical:
    """Empirically tests scripts/measure_architecture_baseline.py execution and metrics."""

    def test_script_execution_and_schema_validation(self):
        """Verify baseline measurement script executes cleanly and produces expected schema."""
        script_path = Path(__file__).parents[1] / "scripts/measure_architecture_baseline.py"
        assert script_path.is_file()

        module_vars = runpy.run_path(str(script_path))
        main = module_vars["main"]
        output_path = module_vars["OUTPUT_PATH"]

        # Execute main function
        main()
        assert output_path.is_file()

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert "javascript_files" in data
        assert "python_files" in data
        assert "fixtures" in data

        # Check golden package metrics
        golden_key = "ifc_to_fds/validation/golden/__init__.py"
        assert golden_key in data["python_files"]
        golden_stats = data["python_files"][golden_key]
        assert golden_stats["total_lines"] == 27
        assert golden_stats["code_lines"] == 25

        # Check all other python targets exist and have lines > 0
        for py_path, stats in data["python_files"].items():
            assert stats["total_lines"] > 0, f"File {py_path} has 0 total lines!"
            assert stats["code_lines"] > 0, f"File {py_path} has 0 code lines!"

        # Check all fixtures have sha256 and positive size
        for fix_path, f_stats in data["fixtures"].items():
            assert len(f_stats["sha256"]) == 64, f"Invalid SHA-256 for {fix_path}"
            assert f_stats["size_bytes"] > 0, f"Empty fixture {fix_path}"

    def test_count_lines_fallback_and_missing_files(self):
        """Verify count_lines dynamic fallback for golden.py and behavior on missing files."""
        script_path = Path(__file__).parents[1] / "scripts/measure_architecture_baseline.py"
        module_vars = runpy.run_path(str(script_path))
        count_lines = module_vars["count_lines"]
        root = module_vars["ROOT"]

        # Missing arbitrary file -> returns zeros
        res_missing = count_lines(root / "non_existent_file.py")
        assert res_missing == {"total_lines": 0, "code_lines": 0}

        # Legacy golden.py path -> dynamically redirected to golden/__init__.py
        legacy_golden = root / "ifc_to_fds/validation/golden.py"
        res_fallback = count_lines(legacy_golden)
        assert res_fallback["total_lines"] == 27
        assert res_fallback["code_lines"] == 25
