"""Regression and unit tests for P0 critical technical debt fixes.

Covers:
- [WP-P0-01] Exported FDS model includes &SURF ID='HVAC' surface definition.
- [WP-P0-02] scripts/measure_architecture_baseline.py path resolution and execution.
- [WP-P0-03] Safe division guard for normal computation on degenerate/zero-area meshes.
"""

import json
from pathlib import Path
import runpy
import warnings
import numpy as np
import pytest

from ifc_to_fds.core.canonical import BoundingBox, CanonicalModel, TriangleMesh
from ifc_to_fds.domain.source.model import SourceMetadata
from ifc_to_fds.domain.scope.model import ScopeDecision
from ifc_to_fds.geometry.mesh import (
    as_trimesh,
    compute_face_normals,
    compute_mesh_normals,
    safe_normalize,
    safe_normalize_normals,
    safe_unit_normals,
)
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.pipeline import prepare
from ifc_to_fds.validation.parser import parse_fds


# ---------------------------------------------------------------------------
# [WP-P0-01] Tests: HVAC Surface Definition in FDS Exporter
# ---------------------------------------------------------------------------


def test_fds_export_includes_hvac_surface_definition_default():
    """Verify default surface block contains &SURF ID='HVAC' with DEFAULT=.FALSE."""
    source = SourceMetadata(
        filename="test.ifc",
        file_path="test.ifc",
        file_hash_sha256="0" * 64,
        file_size_bytes=100,
        schema_version="IFC4",
    )
    model = CanonicalModel(
        schema_version="0.5.0",
        source=source,
        simulation_domain=BoundingBox(xmin=0, xmax=10, ymin=0, ymax=10, zmin=0, zmax=3),
    )
    plan_mapping(model)
    text, manifest = serialize_fds(model)

    assert "&SURF ID='HVAC', COLOR='LIGHT BLUE', DEFAULT=.FALSE. /" in text
    assert "&SURF ID='CONCRETE', COLOR='GRAY', DEFAULT=.TRUE. /" in text

    # Parse exported FDS to verify standard syntax acceptance
    parsed = parse_fds(text)
    assert not parsed.errors
    surf_records = [r for r in parsed.records if r.kind == "SURF"]
    surf_ids = [r.values.get("ID", [None])[0] for r in surf_records if "ID" in r.values]
    assert "HVAC" in surf_ids
    assert "CONCRETE" in surf_ids


def test_fds_export_with_hvac_network_includes_hvac_surface(tmp_path):
    """Verify model with operational HVAC network exports &SURF ID='HVAC' and valid vents."""
    factory = runpy.run_path(str(Path(__file__).parents[1] / "scripts/audit-project-logic.py"))[
        "make_connected_duct_fixture"
    ]
    path = tmp_path / "ducts_p0.ifc"
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
            reviewer="p0_test",
            rationale="Test vent endpoint emission",
            evidence="IFC port",
            hvac=dict(area_m2=0.12, perimeter_m=1.4, endpoints=endpoints),
        )

    plan_mapping(model, decisions=decisions)
    text, manifest = serialize_fds(model)

    assert "&SURF ID='HVAC', COLOR='LIGHT BLUE', DEFAULT=.FALSE. /" in text
    assert "SURF_ID='HVAC'" in text

    parsed = parse_fds(text)
    assert not parsed.errors
    assert any(r.kind == "VENT" and r.values.get("SURF_ID") == ["HVAC"] for r in parsed.operational_records)


# ---------------------------------------------------------------------------
# [WP-P0-02] Tests: Baseline Architecture Metrics Script Path Resolution
# ---------------------------------------------------------------------------


def test_measure_architecture_baseline_targets_exist():
    """Verify all targets in measure_architecture_baseline.py resolve to existing files."""
    script_path = Path(__file__).parents[1] / "scripts/measure_architecture_baseline.py"
    assert script_path.is_file(), f"Script not found at {script_path}"

    module_vars = runpy.run_path(str(script_path))
    py_targets = module_vars["PY_TARGETS"]
    root = module_vars["ROOT"]

    # Must contain the updated golden path
    assert "ifc_to_fds/validation/golden/__init__.py" in py_targets
    assert "ifc_to_fds/validation/golden.py" not in py_targets

    # Every target path must exist on disk
    for rel_path in py_targets:
        full_path = root / rel_path
        assert full_path.is_file(), f"Target file does not exist: {full_path}"

    count_lines = module_vars["count_lines"]
    golden_init = root / "ifc_to_fds/validation/golden/__init__.py"
    data = count_lines(golden_init)
    assert data["total_lines"] > 0
    assert data["code_lines"] > 0

    # Test dynamic fallback resolution for legacy path golden.py
    legacy_path = root / "ifc_to_fds/validation/golden.py"
    fallback_data = count_lines(legacy_path)
    assert fallback_data["total_lines"] == data["total_lines"]
    assert fallback_data["code_lines"] == data["code_lines"]


def test_measure_architecture_baseline_script_execution():
    """Verify running the script main() writes valid JSON with non-zero golden line counts."""
    script_path = Path(__file__).parents[1] / "scripts/measure_architecture_baseline.py"
    module_vars = runpy.run_path(str(script_path))
    main_func = module_vars["main"]
    output_path = module_vars["OUTPUT_PATH"]

    main_func()
    assert output_path.is_file()

    content = json.loads(output_path.read_text(encoding="utf-8"))
    py_files = content["python_files"]
    assert "ifc_to_fds/validation/golden/__init__.py" in py_files
    golden_stats = py_files["ifc_to_fds/validation/golden/__init__.py"]
    assert golden_stats["total_lines"] > 0
    assert golden_stats["code_lines"] > 0


# ---------------------------------------------------------------------------
# [WP-P0-03] Tests: Safe Normal Normalization & Zero-Area Degenerate Meshes
# ---------------------------------------------------------------------------


def test_safe_unit_normals_zero_and_sub_epsilon_vectors():
    """Verify safe vector normalization on zero-length and sub-epsilon vectors."""
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        # Zero vector -> returns default (0, 0, 1)
        z = safe_unit_normals([0.0, 0.0, 0.0])
        assert np.allclose(z, [0.0, 0.0, 1.0])
        assert np.isfinite(z).all()

        # Sub-epsilon vector -> returns default (0, 0, 1)
        sub_eps = safe_unit_normals([1e-15, 0.0, 0.0])
        assert np.allclose(sub_eps, [0.0, 0.0, 1.0])
        assert np.isfinite(sub_eps).all()

        # Standard non-zero vector -> correctly normalized
        normal = safe_unit_normals([0.0, 3.0, 4.0])
        assert np.allclose(normal, [0.0, 0.6, 0.8])
        assert np.isclose(np.linalg.norm(normal), 1.0)

        # Batch 2D array of vectors including zero, degenerate, and valid vectors
        batch = np.array([
            [0.0, 0.0, 0.0],
            [1e-16, 0.0, 1e-16],
            [1.0, 0.0, 0.0],
            [0.0, -5.0, 0.0],
        ])
        norm_batch = safe_unit_normals(batch)
        assert norm_batch.shape == (4, 3)
        assert np.allclose(norm_batch[0], [0.0, 0.0, 1.0])
        assert np.allclose(norm_batch[1], [0.0, 0.0, 1.0])
        assert np.allclose(norm_batch[2], [1.0, 0.0, 0.0])
        assert np.allclose(norm_batch[3], [0.0, -1.0, 0.0])
        assert np.isfinite(norm_batch).all()

        # Check aliases
        assert np.allclose(safe_normalize([0.0, 0.0, 0.0]), [0.0, 0.0, 1.0])
        assert np.allclose(safe_normalize_normals([0.0, 0.0, 0.0]), [0.0, 0.0, 1.0])

    # Zero RuntimeWarnings must be emitted
    runtime_warnings = [w for w in recorded if issubclass(w.category, RuntimeWarning)]
    assert len(runtime_warnings) == 0, [str(w.message) for w in runtime_warnings]


def test_compute_face_normals_degenerate_mesh():
    """Verify compute_face_normals handles zero-area/collinear faces safely without warnings."""
    # Mesh with 1 degenerate collinear face and 1 valid triangle
    mesh = TriangleMesh(
        vertices=[
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],  # Collinear with 0 and 1 -> degenerate
            [0.0, 1.0, 0.0],  # Forms valid triangle with 0 and 1
        ],
        faces=[
            [0, 1, 2],  # Degenerate (area = 0)
            [0, 1, 3],  # Valid face in XY plane, normal = +Z
        ],
    )

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        normals = compute_face_normals(mesh)
        assert normals.shape == (2, 3)
        assert np.isfinite(normals).all()

        # Degenerate face gets default normal [0, 0, 1]
        assert np.allclose(normals[0], [0.0, 0.0, 1.0])

        # Valid face has unit normal along +Z
        assert np.allclose(normals[1], [0.0, 0.0, 1.0])

        # Also test via compute_mesh_normals alias
        normals_alias = compute_mesh_normals(mesh)
        assert np.array_equal(normals, normals_alias)

    runtime_warnings = [w for w in recorded if issubclass(w.category, RuntimeWarning)]
    assert len(runtime_warnings) == 0, [str(w.message) for w in runtime_warnings]


def test_trimesh_zero_volume_mass_properties_no_divide_by_zero():
    """Verify zero-volume trimesh center_mass calculation does not raise divide-by-zero warnings."""
    # Flat 2D triangle has volume = 0
    flat_mesh = TriangleMesh(
        vertices=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        faces=[[0, 1, 2]],
    )
    tm = as_trimesh(flat_mesh)

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        vol = tm.volume
        assert np.isclose(vol, 0.0)
        cm = tm.center_mass
        assert np.isfinite(cm).all()
        # Center of mass should be the triangle centroid [1/3, 1/3, 0]
        assert np.allclose(cm, [1 / 3, 1 / 3, 0.0])

    runtime_warnings = [w for w in recorded if issubclass(w.category, RuntimeWarning)]
    assert len(runtime_warnings) == 0, [str(w.message) for w in runtime_warnings]
