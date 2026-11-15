"""Comprehensive test suite for P1 Architecture & Reliability Work Packages.

Covers:
- WP-P1-01: Placement provenance preservation during origin rebasing (rebase_model_to_origin).
- WP-P1-02: Adaptive CAD tolerance normalization for micro-gaps (1e-6 m) with volume preservation (>99.9%).
- WP-P1-03: Hardened SQLite WAL persistence (PRAGMAs, thread safety, and reconcile_orphaned_jobs).
"""

import json
from pathlib import Path
import threading
import time
import numpy as np
import pytest
import trimesh

from ifc_to_fds.core.canonical import (
    BoundingBox,
    CanonicalElement,
    CanonicalModel,
    GeometryStatus,
    MappingStatus,
    MappingStrategy,
    OpeningReference,
    SourceMetadata,
    TriangleMesh,
)
from ifc_to_fds.core.federation import rebase_model_to_origin
from ifc_to_fds.geometry.mesh import inspect_mesh_quality, valid_solid
from ifc_to_fds.geometry.normalization import (
    CAD_TOLERANCE_M,
    MAX_CAD_DISPLACEMENT_M,
    MAX_DISPLACEMENT_M,
    normalize_element_geometry,
    normalize_source_mesh,
)
from ifc_to_fds.adapters.jobs.repository import JobRepository


def _make_source_metadata(source_id="src1", filename="test.ifc"):
    return SourceMetadata(
        source_id=source_id,
        filename=filename,
        file_path=filename,
        file_hash_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        file_size_bytes=1024,
        schema_version="IFC4",
    )


# ---------------------------------------------------------------------------
# WP-P1-01 Tests: Placement Provenance & Origin Rebase
# ---------------------------------------------------------------------------


def test_rebase_model_to_origin_updates_placement_provenance_numpy_and_list():
    """WP-P1-01: rebase_model_to_origin transforms placement matrices by T(-dx, -dy, -dz)."""
    # Box from [1000, 2000, 0] to [1010, 2010, 3]
    box = trimesh.creation.box(extents=[10, 10, 3])
    box.apply_translation([1005, 2005, 1.5])

    # Element 1: 1D flat list placement (4x4 flattened)
    world_mat_1 = np.eye(4, dtype=float)
    world_mat_1[:3, 3] = [1000.0, 2000.0, 0.0]
    elem1 = CanonicalElement(
        global_id="elem_1",
        step_id=1,
        ifc_type="IfcWall",
        mesh=TriangleMesh(vertices=box.vertices.tolist(), faces=box.faces.tolist()),
        bounding_box=BoundingBox(xmin=1000.0, xmax=1010.0, ymin=2000.0, ymax=2010.0, zmin=0.0, zmax=3.0),
        placement={
            "status": "CONFIRMED",
            "ifc_local_to_model": np.eye(4).ravel().tolist(),
            "model_to_common_world": world_mat_1.ravel().tolist(),
            "effective_world": world_mat_1.ravel().tolist(),
        },
        transform=world_mat_1.ravel().tolist(),
    )

    # Element 2: 2D nested list placement
    world_mat_2 = np.eye(4, dtype=float)
    world_mat_2[:3, 3] = [1005.0, 2005.0, 1.0]
    elem2 = CanonicalElement(
        global_id="elem_2",
        step_id=2,
        ifc_type="IfcColumn",
        mesh=TriangleMesh(vertices=box.vertices.tolist(), faces=box.faces.tolist()),
        bounding_box=BoundingBox(xmin=1000.0, xmax=1010.0, ymin=2000.0, ymax=2010.0, zmin=0.0, zmax=3.0),
        placement={
            "status": "CONFIRMED",
            "effective_world": world_mat_2.tolist(),
        },
        transform=world_mat_2.ravel().tolist(),
    )

    # Element 3: numpy array placement
    world_mat_3 = np.eye(4, dtype=float)
    world_mat_3[:3, 3] = [1010.0, 2010.0, 2.0]
    elem3 = CanonicalElement(
        global_id="elem_3",
        step_id=3,
        ifc_type="IfcBeam",
        mesh=TriangleMesh(vertices=box.vertices.tolist(), faces=box.faces.tolist()),
        bounding_box=BoundingBox(xmin=1000.0, xmax=1010.0, ymin=2000.0, ymax=2010.0, zmin=0.0, zmax=3.0),
        placement={
            "status": "CONFIRMED",
            "effective_world": world_mat_3,
        },
    )

    model = CanonicalModel(
        source=_make_source_metadata("src1", "test.ifc"),
        elements=[elem1, elem2, elem3],
        model_bounds=BoundingBox(xmin=1000.0, xmax=1010.0, ymin=2000.0, ymax=2010.0, zmin=0.0, zmax=3.0),
    )

    dx, dy, dz = 1000.0, 2000.0, 0.0
    rebased_model, applied_vec = rebase_model_to_origin(model, rebase_vector=[dx, dy, dz])

    assert applied_vec == (1000.0, 2000.0, 0.0)
    assert rebased_model.model_bounds.xmin == pytest.approx(0.0)
    assert rebased_model.model_bounds.ymin == pytest.approx(0.0)

    # Verify Element 1: 1D flat list
    eff1 = np.asarray(elem1.placement["effective_world"]).reshape(4, 4)
    local_pt = np.array([0.0, 0.0, 0.0, 1.0])
    rebased_pt1 = eff1 @ local_pt
    assert rebased_pt1[:3] == pytest.approx([0.0, 0.0, 0.0])
    assert isinstance(elem1.placement["effective_world"], list)
    assert len(elem1.placement["effective_world"]) == 16

    # Verify Element 2: 2D nested list
    eff2 = np.asarray(elem2.placement["effective_world"])
    rebased_pt2 = eff2 @ local_pt
    assert rebased_pt2[:3] == pytest.approx([5.0, 5.0, 1.0])
    assert isinstance(elem2.placement["effective_world"], list)
    assert isinstance(elem2.placement["effective_world"][0], list)

    # Verify Element 3: numpy array
    eff3 = elem3.placement["effective_world"]
    assert isinstance(eff3, np.ndarray)
    rebased_pt3 = eff3 @ local_pt
    assert rebased_pt3[:3] == pytest.approx([10.0, 10.0, 2.0])

    # Check that element mesh vertices match the rebased bounding box
    assert min(v[0] for v in elem1.mesh.vertices) == pytest.approx(0.0)
    assert min(v[1] for v in elem1.mesh.vertices) == pytest.approx(0.0)


def test_rebase_model_to_origin_auto_rebase_large_vn2000_coordinates():
    """WP-P1-01: Auto-rebases models with coordinates > 1000 m."""
    box = trimesh.creation.box(extents=[5, 5, 3])
    # VN-2000 coordinate range (e.g. Hanoi / Saigon georeference)
    x_orig, y_orig = 584321.45, 2321456.78
    box.apply_translation([x_orig, y_orig, 10.0])

    world_mat = np.eye(4, dtype=float)
    world_mat[:3, 3] = [x_orig, y_orig, 10.0]

    elem = CanonicalElement(
        global_id="wall_vn2000",
        step_id=10,
        ifc_type="IfcWall",
        mesh=TriangleMesh(vertices=box.vertices.tolist(), faces=box.faces.tolist()),
        bounding_box=BoundingBox(
            xmin=x_orig - 2.5, xmax=x_orig + 2.5,
            ymin=y_orig - 2.5, ymax=y_orig + 2.5,
            zmin=8.5, zmax=11.5,
        ),
        placement={"status": "CONFIRMED", "effective_world": world_mat.ravel().tolist()},
    )

    model = CanonicalModel(
        source=_make_source_metadata("vn2000", "georef.ifc"),
        elements=[elem],
        model_bounds=BoundingBox(
            xmin=x_orig - 2.5, xmax=x_orig + 2.5,
            ymin=y_orig - 2.5, ymax=y_orig + 2.5,
            zmin=8.5, zmax=11.5,
        ),
    )

    rebased, vec = rebase_model_to_origin(model, auto_rebase=True)
    assert vec[0] == pytest.approx(np.floor(x_orig - 2.5))
    assert vec[1] == pytest.approx(np.floor(y_orig - 2.5))
    assert vec[2] == 0.0

    # Bounds must now be near the origin
    assert 0.0 <= rebased.model_bounds.xmin <= 1.0
    assert 0.0 <= rebased.model_bounds.ymin <= 1.0

    # Provenance matrix origin must be shifted by the exact same vector
    eff = np.asarray(elem.placement["effective_world"]).reshape(4, 4)
    assert eff[0, 3] == pytest.approx(x_orig - vec[0])
    assert eff[1, 3] == pytest.approx(y_orig - vec[1])


def test_rebase_model_to_origin_rejects_invalid_vectors():
    """WP-P1-01: Rebase vector validation enforces 3 finite numbers and rejects bools."""
    model = CanonicalModel(
        source=_make_source_metadata("s", "t.ifc"),
        elements=[],
    )
    with pytest.raises(ValueError, match="rebase_vector must be"):
        rebase_model_to_origin(model, rebase_vector=[1, 2])
    with pytest.raises(ValueError, match="rebase_vector must be"):
        rebase_model_to_origin(model, rebase_vector=[True, 0.0, 0.0])
    with pytest.raises(ValueError, match="rebase_vector must be"):
        rebase_model_to_origin(model, rebase_vector=[float("nan"), 0.0, 0.0])


# ---------------------------------------------------------------------------
# WP-P1-02 Tests: Adaptive CAD Tolerance Normalization
# ---------------------------------------------------------------------------


def test_adaptive_cad_tolerance_welds_micro_gaps_into_closed_manifold():
    """WP-P1-02: Micro-gaps (5e-7 m) from CAD tessellation weld cleanly in adaptive mode."""
    box = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    vertices = np.asarray(box.vertices)[np.asarray(box.faces)].reshape(-1, 3)

    # Displace half the vertices by 5e-7 m (0.5 micrometre), typical OpenCASCADE CAD tolerance
    vertices[::2] += 5e-7
    raw_mesh = TriangleMesh(
        vertices=vertices.tolist(),
        faces=np.arange(len(vertices)).reshape(-1, 3).tolist(),
    )

    # In strict ULP mode (1e-12 m), this gap is rejected as an unclosed boundary
    _, strict_proof = normalize_source_mesh(raw_mesh, adaptive_cad=False)
    assert strict_proof["status"] == "REFUSED"
    assert strict_proof["reason"] == "SOURCE_SURFACE_REMAINS_OPEN"

    # In adaptive CAD mode, normalize_element_geometry welds micro-gaps cleanly
    normalized, adaptive_proof = normalize_element_geometry(raw_mesh)
    assert adaptive_proof["status"] == "NORMALIZED"
    assert bool(adaptive_proof["result_quality"]["is_closed_manifold"]) is True
    assert adaptive_proof["result_quality"]["open_edges"] == 0
    assert 0 < adaptive_proof["max_vertex_displacement_m"] <= CAD_TOLERANCE_M
    assert adaptive_proof["volume_ratio"] > 0.999
    assert valid_solid(normalized)


def test_adaptive_cad_tolerance_preserves_real_architectural_openings():
    """WP-P1-02: Real gaps (e.g. 1 cm = 0.01 m or 1 mm = 0.001 m) are NOT silently resealed."""
    box = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    vertices = np.asarray(box.vertices)[np.asarray(box.faces)].reshape(-1, 3)

    # Introduce a real architectural gap of 2 mm (0.002 m), far above CAD tolerance (1e-6 m)
    vertices[0][0] += 0.002
    raw_mesh = TriangleMesh(
        vertices=vertices.tolist(),
        faces=np.arange(len(vertices)).reshape(-1, 3).tolist(),
    )

    # Even with adaptive CAD tolerance, real openings must NOT be sealed
    _, proof = normalize_element_geometry(raw_mesh)
    assert proof["status"] == "REFUSED"
    assert proof["reason"] == "SOURCE_SURFACE_REMAINS_OPEN"


def test_normalize_element_geometry_with_canonical_element():
    """WP-P1-02: Accepts CanonicalElement directly, updating mesh and geometry_status."""
    box = trimesh.creation.box()
    vertices = np.asarray(box.vertices)[np.asarray(box.faces)].reshape(-1, 3)
    vertices[::2] += 4e-7
    mesh = TriangleMesh(vertices=vertices.tolist(), faces=np.arange(len(vertices)).reshape(-1, 3).tolist())

    elem = CanonicalElement(
        global_id="elem_cad_test",
        step_id=101,
        ifc_type="IfcWall",
        mesh=mesh,
        geometry_status=GeometryStatus.NOT_PROCESSED,
    )

    res_elem, proof = normalize_element_geometry(elem)
    assert proof["status"] == "NORMALIZED"
    assert res_elem.geometry_status == GeometryStatus.VALID
    assert valid_solid(res_elem.mesh)


# ---------------------------------------------------------------------------
# WP-P1-03 Tests: SQLite WAL Persistence & Durability
# ---------------------------------------------------------------------------


def test_sqlite_wal_pragmas_on_every_connection(tmp_path):
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


def test_reconcile_orphaned_jobs_recovers_crashed_workers(tmp_path):
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


def test_sqlite_concurrent_thread_safety(tmp_path):
    """WP-P1-03: Multi-threaded concurrent reads/writes operate without SQLite locking crashes."""
    repo = JobRepository(root=tmp_path)
    errors = []

    def worker_thread(tid: int):
        try:
            for i in range(15):
                jid = f"thread-job-{tid}-{i}"
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
