"""Adversarial stress and durability challenge test suite for WP-P1-03.

Designed by Challenger 2 to empirically test:
1. SQLite WAL Durability & Multi-Process/Multi-Thread Concurrency:
   - High-concurrency thread stress (20 threads, heavy interleaved set/get/snapshot/delete).
   - Multi-process concurrency: multiple distinct OS processes accessing the same SQLite WAL database concurrently.
   - SQLite PRAGMA integrity check and transaction consistency under high load.
2. Crash Recovery & Orphaned Job Reconciliation:
   - Abrupt worker termination simulation with partial artifacts (partial progress.json, temp files).
   - Missing job directories, pre-existing diagnostics, None started timestamps, timeout_seconds thresholding.
   - Non-running jobs (QUEUED, COMPLETED) remain untouched.
   - Persistence verification across fresh JobRepository instances.
   - Snapshot URL verification for generated diagnostics artifacts.
"""

from contextlib import closing
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
from typing import List, Optional, Tuple
import pytest

from ifc_to_fds.adapters import sqlite_wal
from ifc_to_fds.server.job_repository import JobRepository


# ---------------------------------------------------------------------------
# Helpers for multi-process worker simulation
# ---------------------------------------------------------------------------


def _mp_worker_task(db_root_str: str, worker_id: int, num_jobs: int) -> Tuple[int, List[str]]:
    """Worker task run in an isolated OS process."""
    errors = []
    try:
        repo = JobRepository(root=Path(db_root_str))
        for i in range(num_jobs):
            jid = f"mp-job-{worker_id}-{i}"
            jdir = Path(db_root_str) / jid
            jdir.mkdir(parents=True, exist_ok=True)
            (jdir / "progress.json").write_text(json.dumps({"step": i, "worker": worker_id}), encoding="utf-8")

            # 1. Insert RUNNING job
            repo.set(jid, {
                "id": jid,
                "state": "RUNNING",
                "directory": str(jdir),
                "mode": "convert",
                "created": time.time(),
                "started": time.time(),
                "durable": True,
            })

            # 2. Query snapshot
            snap = repo.snapshot(jid)
            if snap.get("id") != jid:
                errors.append(f"Worker {worker_id} snapshot mismatch on {jid}")

            # 3. Update job to COMPLETED
            job = repo.get(jid)
            if job is None:
                errors.append(f"Worker {worker_id} failed to get {jid}")
            else:
                job["state"] = "COMPLETED"
                job["finished"] = time.time()
                (jdir / "result.json").write_text(json.dumps({"status": "SUCCESS", "artifacts": {}}), encoding="utf-8")
                repo.set(jid, job)

            # Micro-pause to interleave with other processes
            time.sleep(0.002)

    except Exception as exc:
        import traceback
        errors.append(f"Worker {worker_id} crashed with: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")

    return worker_id, errors


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_wal_initialization_retries_after_sqlite_releases_an_exclusive_lock(tmp_path, monkeypatch):
    database = tmp_path / "journal.sqlite3"
    with closing(sqlite3.connect(str(database))) as holder, closing(
        sqlite3.connect(str(database), timeout=0)
    ) as contender:
        holder.execute("CREATE TABLE example (id INTEGER)")
        holder.commit()
        holder.execute("BEGIN EXCLUSIVE")
        retries = []

        def release_lock(delay):
            retries.append(delay)
            holder.commit()

        monkeypatch.setattr(sqlite_wal, "sleep", release_lock)
        sqlite_wal.enable_wal(contender)
        assert len(retries) == 1

    with closing(sqlite3.connect(str(database))) as reopened:
        assert reopened.execute("PRAGMA journal_mode;").fetchone()[0] == "wal"


def test_sqlite_wal_multi_process_concurrency(tmp_path):
    """Stress test: 4 separate OS processes concurrently write/update to the same SQLite WAL database."""
    num_processes = 4
    jobs_per_process = 25
    expected_total_jobs = num_processes * jobs_per_process

    # Use multiprocessing pool to spawn genuine separate OS processes
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=num_processes) as pool:
        args = [(str(tmp_path), p_idx, jobs_per_process) for p_idx in range(num_processes)]
        results = pool.starmap(_mp_worker_task, args)

    all_errors = []
    for wid, errs in results:
        all_errors.extend(errs)

    assert not all_errors, f"Multi-process concurrency produced errors: {all_errors}"

    # Verify SQLite WAL database integrity directly via sqlite3 PRAGMA
    db_file = tmp_path / "jobs.sqlite3"
    assert db_file.is_file(), "jobs.sqlite3 must exist"

    conn = sqlite3.connect(str(db_file))
    integrity = conn.execute("PRAGMA integrity_check;").fetchall()
    assert integrity == [("ok",)], f"SQLite integrity check failed: {integrity}"

    journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0].upper()
    assert journal_mode == "WAL", f"Expected WAL journal mode, got {journal_mode}"

    row_count = conn.execute("SELECT count(*) FROM jobs;").fetchone()[0]
    assert row_count == expected_total_jobs, f"Expected {expected_total_jobs} rows in SQLite, found {row_count}"

    states = conn.execute("SELECT DISTINCT state FROM jobs;").fetchall()
    assert set(s[0] for s in states) == {"COMPLETED"}, f"Expected all jobs COMPLETED, got {states}"
    conn.close()

def _init_worker_proc(db_root_str: str, worker_id: int) -> Tuple[int, Optional[str]]:
    try:
        # Initialize repo on brand new DB concurrently
        repo = JobRepository(root=Path(db_root_str))
        jid = f"init-job-{worker_id}"
        repo.set(jid, {"id": jid, "state": "QUEUED"})
        return worker_id, None
    except Exception as exc:
        import traceback
        return worker_id, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"


def test_sqlite_concurrent_multiprocess_initialization(tmp_path):
    """Stress test: 8 separate OS processes simultaneously initializing JobRepository
    on the exact same newly created directory at the exact same moment.
    Tests whether _init_db and _get_connection PRAGMAs handle multi-process initialization races.
    """
    num_processes = 8
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=num_processes) as pool:
        args = [(str(tmp_path), i) for i in range(num_processes)]
        results = pool.starmap(_init_worker_proc, args)

    errors = [err for _, err in results if err is not None]
    assert not errors, f"Concurrent initialization failed with: {errors}"



def test_sqlite_high_thread_contention(tmp_path):
    """Stress test: 20 threads performing rapid set, get, snapshot, update and delete operations."""
    repo = JobRepository(root=tmp_path)
    num_threads = 20
    ops_per_thread = 20
    errors = []

    def stress_worker(tid: int):
        try:
            for i in range(ops_per_thread):
                jid = f"stress-th-{tid}-{i}"
                jdir = tmp_path / jid
                jdir.mkdir(parents=True, exist_ok=True)
                (jdir / "progress.json").write_text(json.dumps({"step": i}), encoding="utf-8")

                # Insert
                repo.set(jid, {
                    "id": jid,
                    "state": "QUEUED",
                    "directory": str(jdir),
                    "created": time.time(),
                })

                # Transition to RUNNING
                j = repo.get(jid)
                if j:
                    j["state"] = "RUNNING"
                    j["started"] = time.time()
                    repo.set(jid, j)

                # Snapshot check
                _ = repo.snapshot(jid)

                # Every 5th job: delete it to stress DELETE concurrency
                if i % 5 == 0:
                    repo.delete(jid)
                    assert not repo.contains(jid)
                else:
                    j["state"] = "COMPLETED"
                    j["finished"] = time.time()
                    repo.set(jid, j)

        except Exception as exc:
            errors.append((tid, exc))

    threads = [threading.Thread(target=stress_worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread contention produced exceptions: {errors}"

    # Verify count and integrity
    expected_surviving = num_threads * (ops_per_thread - (ops_per_thread // 5))
    assert len(repo.all_jobs()) == expected_surviving

    # Verify persistence via new instance
    fresh_repo = JobRepository(root=tmp_path)
    assert len(fresh_repo.all_jobs()) == expected_surviving


def test_crash_recovery_matrix_and_diagnostics(tmp_path):
    """Exhaustive test for reconcile_orphaned_jobs covering all edge cases:
    - Case 1: Standard RUNNING job with partial progress.json artifact -> Transitions to FAILED, diagnostics created.
    - Case 2: RUNNING job with existing diagnostics.json -> Transitions to FAILED, diagnostics NOT overwritten.
    - Case 3: RUNNING job with missing directory -> Handled gracefully without crash, state updated to FAILED.
    - Case 4: RUNNING job with started=None -> Handled cleanly without crash, transitioned to FAILED.
    - Case 5: RUNNING job within timeout_seconds -> Ignored (retains RUNNING).
    - Case 6: RUNNING job past timeout_seconds -> Transitions to FAILED.
    - Case 7: QUEUED and COMPLETED jobs -> Untouched.
    """
    repo = JobRepository(root=tmp_path)
    now = time.time()

    # Case 1: Standard crashed job with partial progress
    c1_dir = tmp_path / "crashed-1"
    c1_dir.mkdir(parents=True, exist_ok=True)
    (c1_dir / "progress.json").write_text(json.dumps({"stage": "GEOM_TESSELLATION", "pct": 45}), encoding="utf-8")
    repo.set("crashed-1", {
        "id": "crashed-1",
        "state": "RUNNING",
        "directory": str(c1_dir),
        "created": now - 200,
        "started": now - 180,
    })

    # Case 2: Pre-existing diagnostics file
    c2_dir = tmp_path / "crashed-2"
    c2_dir.mkdir(parents=True, exist_ok=True)
    custom_diag = {"job_id": "crashed-2", "error_type": "CustomPreExistingError", "message": "OOM"}
    (c2_dir / "diagnostics.json").write_text(json.dumps(custom_diag), encoding="utf-8")
    repo.set("crashed-2", {
        "id": "crashed-2",
        "state": "RUNNING",
        "directory": str(c2_dir),
        "created": now - 300,
        "started": now - 250,
    })

    # Case 3: Non-existent directory
    repo.set("crashed-3-no-dir", {
        "id": "crashed-3-no-dir",
        "state": "RUNNING",
        "directory": str(tmp_path / "non_existent_folder"),
        "created": now - 300,
        "started": now - 280,
    })

    # Case 4: started is None
    c4_dir = tmp_path / "crashed-4-no-started"
    c4_dir.mkdir(parents=True, exist_ok=True)
    repo.set("crashed-4-no-started", {
        "id": "crashed-4-no-started",
        "state": "RUNNING",
        "directory": str(c4_dir),
        "created": now - 50,
        "started": None,
    })

    # Case 5: Job started 10s ago, within timeout_seconds=60
    c5_dir = tmp_path / "active-recent"
    c5_dir.mkdir(parents=True, exist_ok=True)
    repo.set("active-recent", {
        "id": "active-recent",
        "state": "RUNNING",
        "directory": str(c5_dir),
        "created": now - 15,
        "started": now - 10,
    })

    # Case 6: Job started 120s ago, past timeout_seconds=60
    c6_dir = tmp_path / "crashed-timeout"
    c6_dir.mkdir(parents=True, exist_ok=True)
    repo.set("crashed-timeout", {
        "id": "crashed-timeout",
        "state": "RUNNING",
        "directory": str(c6_dir),
        "created": now - 130,
        "started": now - 120,
    })

    # Case 7a: QUEUED job (must not be modified)
    repo.set("queued-job", {
        "id": "queued-job",
        "state": "QUEUED",
        "directory": str(tmp_path / "queued"),
        "created": now - 10,
    })

    # Case 7b: COMPLETED job (must not be modified)
    repo.set("completed-job", {
        "id": "completed-job",
        "state": "COMPLETED",
        "directory": str(tmp_path / "completed"),
        "created": now - 100,
        "finished": now - 50,
    })

    # Execute reconciliation with timeout_seconds=60
    reconciled = repo.reconcile_orphaned_jobs(timeout_seconds=60.0)

    # Expected reconciled: crashed-1, crashed-2, crashed-3-no-dir, crashed-4-no-started, crashed-timeout
    expected_reconciled = {"crashed-1", "crashed-2", "crashed-3-no-dir", "crashed-4-no-started", "crashed-timeout"}
    assert set(reconciled) == expected_reconciled

    # Verify active-recent remains RUNNING
    assert repo.get("active-recent")["state"] == "RUNNING"

    # Verify queued-job and completed-job untouched
    assert repo.get("queued-job")["state"] == "QUEUED"
    assert repo.get("completed-job")["state"] == "COMPLETED"

    # Verify Case 1 diagnostics file created
    diag1 = json.loads((c1_dir / "diagnostics.json").read_text(encoding="utf-8"))
    assert diag1["job_id"] == "crashed-1"
    assert diag1["error_type"] == "AbortError"
    assert "Worker process restarted while job was in progress" in diag1["message"]

    # Verify Case 2 diagnostics was NOT overwritten
    diag2 = json.loads((c2_dir / "diagnostics.json").read_text(encoding="utf-8"))
    assert diag2["error_type"] == "CustomPreExistingError"

    # Verify snapshot exposes diagnostics_url for reconciled job with diagnostics
    snap1 = repo.snapshot("crashed-1")
    assert snap1.get("diagnostics_url") == "/api/jobs/crashed-1/diagnostics"

    # Verify persistence across restart
    restarted_repo = JobRepository(root=tmp_path)
    for jid in expected_reconciled:
        persisted = restarted_repo.get(jid)
        assert persisted["state"] == "FAILED"
        assert "Worker process restarted while job was in progress" in persisted["error"]

    assert restarted_repo.get("active-recent")["state"] == "RUNNING"
    assert restarted_repo.get("queued-job")["state"] == "QUEUED"
    assert restarted_repo.get("completed-job")["state"] == "COMPLETED"


def test_real_subprocess_killed_worker_crash_recovery(tmp_path):
    """Live process kill test:
    Launch an external child process that writes partial artifacts and updates status to RUNNING.
    Forcefully kill the child process (SIGKILL / terminate).
    Verify that reconcile_orphaned_jobs detects the orphaned job, marks it FAILED,
    creates diagnostics.json, and persists correctly across server restarts.
    """
    repo = JobRepository(root=tmp_path)
    jid = "killed-worker-job"
    jdir = tmp_path / jid
    jdir.mkdir(parents=True, exist_ok=True)

    # Prepare child worker script that registers RUNNING, writes partial artifact, and sleeps waiting to be killed
    worker_script = f"""
import json
import os
import sys
import time
from pathlib import Path

jdir = Path(r"{jdir}")
(jdir / "progress.json").write_text(json.dumps({{"stage": "GEOM_SLICING", "percent": 30}}), encoding="utf-8")
(jdir / "partial_mesh.tmp").write_text("PARTIAL_GEOMETRY_DATA", encoding="utf-8")

# Signal parent that worker has started
(jdir / "worker_started.flag").write_text("1", encoding="utf-8")

# Block indefinitely until killed
while True:
    time.sleep(0.1)
"""
    # Set job state in repository to RUNNING
    start_time = time.time()
    repo.set(jid, {
        "id": jid,
        "state": "RUNNING",
        "directory": str(jdir),
        "created": start_time - 10,
        "started": start_time - 5,
        "mode": "convert",
    })

    proc = subprocess.Popen([sys.executable, "-c", worker_script])
    try:
        # Wait until worker creates the flag file
        flag = jdir / "worker_started.flag"
        waited = 0
        while not flag.is_file() and waited < 50:
            time.sleep(0.1)
            waited += 1

        assert flag.is_file(), "Worker process did not start in time"
        assert (jdir / "partial_mesh.tmp").is_file(), "Partial artifact must exist before crash"
        assert repo.get(jid)["state"] == "RUNNING"

        # Forcefully terminate worker process (simulating SIGKILL / crash)
        proc.kill()
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()

    # Now simulate server reboot / recovery run
    recovered_ids = repo.reconcile_orphaned_jobs()
    assert jid in recovered_ids

    # Verify job status and diagnostic output
    job = repo.get(jid)
    assert job["state"] == "FAILED"
    assert "Worker process restarted while job was in progress" in job["error"]

    diag_file = jdir / "diagnostics.json"
    assert diag_file.is_file()
    diag = json.loads(diag_file.read_text(encoding="utf-8"))
    assert diag["job_id"] == jid
    assert diag["error_type"] == "AbortError"

    # Verify durability across fresh repository instance
    rebooted = JobRepository(root=tmp_path)
    rebooted_job = rebooted.get(jid)
    assert rebooted_job["state"] == "FAILED"
    assert "Worker process restarted while job was in progress" in rebooted_job["error"]

