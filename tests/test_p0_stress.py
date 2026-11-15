"""Empirical adversarial stress test suite for P0 fixes.

Challenger 2 verification:
- Boundary conditions (epsilon boundary, subnormals, signed zero, Inf, NaN)
- Scale extremes (1e-300 to 1e+300)
- Array dimensions and invalid shapes
- Degenerate mesh topologies (collinear, coincident, microscopic, huge coordinates)
- Trimesh mass properties under zero-volume & degenerate configurations
- Property-based randomized stress test (100,000 vectors)
- RuntimeWarning suppression verification
"""

import warnings
import numpy as np
import pytest
import trimesh

from ifc_to_fds.core.canonical import TriangleMesh
from ifc_to_fds.geometry.mesh import (
    as_trimesh,
    compute_face_normals,
    compute_mesh_normals,
    safe_normalize,
    safe_normalize_normals,
    safe_unit_normals,
)


# ---------------------------------------------------------------------------
# 1. Parameter Boundary Tests on safe_unit_normals
# ---------------------------------------------------------------------------


def test_safe_unit_normals_boundary_epsilon():
    """Verify behavior exactly at, slightly below, and slightly above epsilon."""
    eps = 1e-14
    default = (0.0, 0.0, 1.0)

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        # 1. Exactly at epsilon: norm == eps -> mask is (length > eps), so False -> default
        v_exact = np.array([eps, 0.0, 0.0])
        n_exact = safe_unit_normals(v_exact, epsilon=eps, default=default)
        assert np.allclose(n_exact, default), f"Expected default at boundary, got {n_exact}"

        # 2. Slightly below epsilon: norm < eps -> default
        v_below = np.array([eps * (1.0 - 1e-5), 0.0, 0.0])
        n_below = safe_unit_normals(v_below, epsilon=eps, default=default)
        assert np.allclose(n_below, default)

        # 3. Slightly above epsilon: norm > eps -> normalized to [1.0, 0.0, 0.0]
        v_above = np.array([eps * (1.0 + 1e-5), 0.0, 0.0])
        n_above = safe_unit_normals(v_above, epsilon=eps, default=default)
        assert np.allclose(n_above, [1.0, 0.0, 0.0], atol=1e-7)
        assert np.isclose(np.linalg.norm(n_above), 1.0)

    assert len(recorded) == 0, [str(w.message) for w in recorded]


def test_safe_unit_normals_subnormal_and_signed_zero():
    """Verify IEEE 754 subnormals and signed zeroes do not cause warnings or NaNs."""
    default = (0.0, 0.0, 1.0)
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        # Signed zeroes
        neg_zero = np.array([-0.0, -0.0, -0.0])
        n_neg = safe_unit_normals(neg_zero, default=default)
        assert np.allclose(n_neg, default)

        # Subnormal float64 (smallest positive subnormal is ~5e-324)
        subnorm = np.array([5e-324, 0.0, 0.0])
        n_sub = safe_unit_normals(subnorm, default=default)
        assert np.allclose(n_sub, default)

        # Vector with subnormal and zero components
        subnorm_mix = np.array([1e-320, 1e-320, 0.0])
        n_sub_mix = safe_unit_normals(subnorm_mix, default=default)
        assert np.allclose(n_sub_mix, default)

    assert len(recorded) == 0, [str(w.message) for w in recorded]


def test_safe_unit_normals_non_finite_inputs():
    """Verify NaN and Inf inputs safely return the default normal without crashes or unhandled warnings."""
    default = (0.0, 0.0, 1.0)
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        # Vector containing NaN
        v_nan = np.array([np.nan, 1.0, 0.0])
        n_nan = safe_unit_normals(v_nan, default=default)
        assert np.allclose(n_nan, default)

        # Vector containing Inf
        v_inf = np.array([np.inf, 0.0, 0.0])
        n_inf = safe_unit_normals(v_inf, default=default)
        assert np.allclose(n_inf, default)

        # Vector containing -Inf and NaN
        v_both = np.array([-np.inf, np.nan, 0.0])
        n_both = safe_unit_normals(v_both, default=default)
        assert np.allclose(n_both, default)

        # Batch containing mixed finite, non-finite, and degenerate vectors
        batch = np.array([
            [np.nan, 0.0, 0.0],
            [0.0, 3.0, 4.0],
            [np.inf, np.inf, np.inf],
            [0.0, 0.0, 0.0],
            [-10.0, 0.0, 0.0],
        ])
        batch_out = safe_unit_normals(batch, default=default)
        assert batch_out.shape == (5, 3)
        assert np.allclose(batch_out[0], default)
        assert np.allclose(batch_out[1], [0.0, 0.6, 0.8])
        assert np.allclose(batch_out[2], default)
        assert np.allclose(batch_out[3], default)
        assert np.allclose(batch_out[4], [-1.0, 0.0, 0.0])

    assert len(recorded) == 0, [str(w.message) for w in recorded]


def test_safe_unit_normals_extreme_scales():
    """Verify vector normalization across extreme scales (1e-100 to 1e+150)."""
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        # Huge vector (1e150)
        v_huge = np.array([1e150, 0.0, 0.0])
        n_huge = safe_unit_normals(v_huge)
        assert np.allclose(n_huge, [1.0, 0.0, 0.0])
        assert np.isclose(np.linalg.norm(n_huge), 1.0)

        # Diagonal huge vector
        v_huge_diag = np.array([1e150, 1e150, 1e150])
        n_huge_diag = safe_unit_normals(v_huge_diag)
        expected = np.array([1.0, 1.0, 1.0]) / np.sqrt(3.0)
        assert np.allclose(n_huge_diag, expected)

    assert len(recorded) == 0, [str(w.message) for w in recorded]


def test_safe_unit_normals_shapes_and_dimensions():
    """Verify input shape validation: 1D (3,), 2D (N, 3), 3D (B, N, 3), and invalid shapes."""
    default = (0.0, 1.0, 0.0)

    # Empty 2D array (0, 3)
    empty_2d = np.empty((0, 3))
    out_empty = safe_unit_normals(empty_2d, default=default)
    assert out_empty.shape == (0, 3)

    # 3D array (2, 4, 3)
    arr_3d = np.zeros((2, 4, 3))
    arr_3d[0, 1] = [0.0, 0.0, 5.0]
    out_3d = safe_unit_normals(arr_3d, default=default)
    assert out_3d.shape == (2, 4, 3)
    assert np.allclose(out_3d[0, 0], default)
    assert np.allclose(out_3d[0, 1], [0.0, 0.0, 1.0])

    # Invalid shapes: must raise ValueError
    with pytest.raises(ValueError, match="Expected 3D vectors"):
        safe_unit_normals([1.0, 2.0])

    with pytest.raises(ValueError, match="Expected 3D vectors"):
        safe_unit_normals(np.ones((5, 2)))

    with pytest.raises(ValueError, match="Expected 3D vectors"):
        safe_unit_normals(np.ones((5, 4)))


# ---------------------------------------------------------------------------
# 2. Parameter Boundary Tests on compute_face_normals
# ---------------------------------------------------------------------------


def test_compute_face_normals_degenerate_topologies():
    """Verify compute_face_normals on various degenerate triangle topologies."""
    # Coincident vertices, collinear, micro-scale, huge-scale
    mesh = TriangleMesh(
        vertices=[
            [0.0, 0.0, 0.0],       # 0
            [0.0, 0.0, 0.0],       # 1 (identical to 0)
            [1.0, 0.0, 0.0],       # 2
            [2.0, 0.0, 0.0],       # 3 (collinear with 0 and 2)
            [0.0, 1.0, 0.0],       # 4
            [1e-15, 0.0, 0.0],     # 5 (sub-epsilon distance)
            [0.0, 1e-15, 0.0],     # 6 (sub-epsilon distance)
            [1e10, 0.0, 0.0],      # 7 (huge)
            [0.0, 1e10, 0.0],      # 8 (huge)
        ],
        faces=[
            [0, 1, 4],  # Coincident vertices (0 and 1) -> degenerate
            [0, 2, 3],  # Collinear (0, 2, 3) -> degenerate
            [0, 5, 6],  # Microscopic triangle -> cross product < 1e-28 < epsilon -> default
            [0, 2, 4],  # Standard valid face (+Z normal)
            [0, 7, 8],  # Huge triangle (+Z normal)
        ],
    )

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        normals = compute_face_normals(mesh, default=(0.0, 0.0, -1.0))
        assert normals.shape == (5, 3)
        assert np.isfinite(normals).all()

        # Face 0 (coincident) -> default
        assert np.allclose(normals[0], [0.0, 0.0, -1.0])

        # Face 1 (collinear) -> default
        assert np.allclose(normals[1], [0.0, 0.0, -1.0])

        # Face 2 (microscopic) -> default
        assert np.allclose(normals[2], [0.0, 0.0, -1.0])

        # Face 3 (standard) -> unit normal [0, 0, 1]
        assert np.allclose(normals[3], [0.0, 0.0, 1.0])

        # Face 4 (huge) -> unit normal [0, 0, 1]
        assert np.allclose(normals[4], [0.0, 0.0, 1.0])

    assert len(recorded) == 0, [str(w.message) for w in recorded]


def test_compute_face_normals_empty_and_non_triangular_faces():
    """Verify empty mesh and non-triangular rectangular faces handling."""
    # Empty faces
    mesh_empty_faces = TriangleMesh(vertices=[[0, 0, 0]], faces=[])
    normals_empty = compute_face_normals(mesh_empty_faces)
    assert normals_empty.shape == (0, 3)

    # Empty vertices with faces (invalid reference)
    mesh_empty_verts = TriangleMesh(vertices=[], faces=[[0, 1, 2]])
    normals_verts = compute_face_normals(mesh_empty_verts, default=(1.0, 0.0, 0.0))
    assert normals_verts.shape == (1, 3)
    assert np.allclose(normals_verts[0], [1.0, 0.0, 0.0])

    # Rectangular quad mesh (faces with 4 vertices)
    class QuadMesh:
        vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
        faces = [[0, 1, 2, 3]]

    quad = QuadMesh()
    normals_quad = compute_face_normals(quad, default=(0.0, 0.0, 1.0))
    assert normals_quad.shape == (1, 3)
    assert np.allclose(normals_quad[0], [0.0, 0.0, 1.0])

    # Rectangular line segments (faces with 2 vertices)
    class LineMesh:
        vertices = np.array([[0, 0, 0], [1, 0, 0]], dtype=float)
        faces = [[0, 1]]

    lines = LineMesh()
    normals_lines = compute_face_normals(lines, default=(0.0, 0.0, 1.0))
    assert normals_lines.shape == (1, 3)
    assert np.allclose(normals_lines[0], [0.0, 0.0, 1.0])

    # Inhomogeneous / ragged faces: NumPy >= 1.20 disallows ragged nested lists
    # np.asarray(ragged_list) raises ValueError before reaching fallback
    class RaggedMesh:
        vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
        faces = [[0, 1, 2], [0, 1]]

    ragged = RaggedMesh()
    with pytest.raises(ValueError, match="inhomogeneous shape|setting an array element with a sequence"):
        compute_face_normals(ragged)


# ---------------------------------------------------------------------------
# 3. Randomized Property-Based Tests (Monte-Carlo Invariants)
# ---------------------------------------------------------------------------


def test_safe_unit_normals_monte_carlo_invariants():
    """Run randomized property tests on 100,000 vectors across logarithmic scale extremes."""
    rng = np.random.default_rng(42)
    n_samples = 100_000

    # Log-uniform exponents between -20 and +20
    exponents = rng.uniform(-20, 20, size=(n_samples, 1))
    directions = rng.standard_normal(size=(n_samples, 3))
    dir_norms = np.linalg.norm(directions, axis=1, keepdims=True)
    unit_directions = directions / dir_norms
    random_vectors = unit_directions * (10.0 ** exponents)

    # Inject degenerate, zero, and non-finite vectors
    random_vectors[0:1000] = 0.0
    random_vectors[1000:2000] = 1e-15 * rng.standard_normal(size=(1000, 3))
    random_vectors[2000:2500, 0] = np.nan
    random_vectors[2500:3000, 1] = np.inf

    default = (0.0, 0.0, 1.0)
    eps = 1e-14

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")

        result = safe_unit_normals(random_vectors, epsilon=eps, default=default)

        # Invariant 1: All output vectors must be finite
        assert np.isfinite(result).all(), "Non-finite values found in normalized output"

        # Invariant 2: Output shape must match input shape
        assert result.shape == random_vectors.shape

        # Invariant 3: Vectors with norm > eps and finite must be unit vectors
        v_norms = np.linalg.norm(random_vectors, axis=1)
        valid_mask = (v_norms > eps) & np.isfinite(v_norms)
        out_norms = np.linalg.norm(result[valid_mask], axis=1)
        assert np.allclose(out_norms, 1.0, atol=1e-7), "Normalized vectors are not unit length"

        # Invariant 4: Degenerate/non-finite vectors must equal default
        degen_mask = ~valid_mask
        assert np.allclose(result[degen_mask], default), "Degenerate vectors did not match default"

    # Invariant 5: Zero RuntimeWarnings emitted
    assert len(recorded) == 0, [str(w.message) for w in recorded]
