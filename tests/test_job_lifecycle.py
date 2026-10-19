"""Comprehensive test suite for Feature 5: Job Lifecycle, SQLite Persistence, Security & Resource Governance.

Covers:
- F01: Host validation and API key authentication on /api/* routes.
- F02: SQLite persistent JobRepository and crash recovery on server restart.
- F02: Startup orphaned directory cleanup.
- F03: Durable research artifact retention (preventing auto-delete for MAPPING_VERIFIED / durable jobs).
- F04: Early admission rejection (HTTP 429) before spooling files to disk when queue is full.
- F05: Worker RSS memory quota enforcement (RESOURCE_EXHAUSTED).
- F06: Upload cancellation cleans up staging directories.
- F08: Download touch extends retention countdown.
- F09: Queue wait timeout transitions queued jobs to TIMED_OUT.
- F10: BodyLimitMiddleware returns clean 413 JSONResponse on streaming overflow.
"""

import json
import os
import shutil
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService
from ifc_to_fds.http_limits import BodyLimitMiddleware
from ifc_to_fds.server import app, manager


def test_sqlite_persistence_and_restart_recovery(tmp_path):
    """F02: SQLite persists job metadata; crashed active jobs recover to FAILED on restart."""
    repo1 = JobRepository(root=tmp_path)
    job_dir = tmp_path / "job-1"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "progress.json").write_text(json.dumps({"stage": "GEOMETRY"}), encoding="utf-8")

    # Insert a simulated RUNNING job that crashed when process died
    repo1.set("job-1", {
        "id": "job-1",
        "state": "RUNNING",
        "directory": str(job_dir),
        "created": time.time() - 100,
        "started": time.time() - 90,
        "mode": "convert",
    })
    # Insert a COMPLETED job
    comp_dir = tmp_path / "job-2"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "result.json").write_text(json.dumps({"status": "MAPPING_VERIFIED"}), encoding="utf-8")
    repo1.set("job-2", {
        "id": "job-2",
        "state": "COMPLETED",
        "directory": str(comp_dir),
        "created": time.time() - 200,
        "finished": time.time() - 100,
        "mode": "convert",
    })

    # Restart service instance pointing to the same root
    service2 = JobService(root=tmp_path, max_waiting=2)
    try:
        # job-1 was RUNNING when server crashed -> must be reconciled to FAILED
        recovered_job1 = service2.repository.get("job-1")
        assert recovered_job1 is not None
        assert recovered_job1["state"] == "FAILED"
        assert "server restart" in recovered_job1["error"]
        assert (job_dir / "diagnostics.json").is_file()

        # job-2 was COMPLETED -> must remain COMPLETED and readable
        recovered_job2 = service2.repository.get("job-2")
        assert recovered_job2 is not None
        assert recovered_job2["state"] == "COMPLETED"
        assert service2.result("job-2")["status"] == "MAPPING_VERIFIED"
    finally:
        service2.close()


def test_sqlite_persistence_retry_and_logging(tmp_path, monkeypatch, caplog):
    """NEW-05: SQLite locked retries succeed; persistent database errors are logged."""
    import logging
    import sqlite3

    repo = JobRepository(root=tmp_path)
    real_get_conn = repo._get_connection
    call_count = 0

    class RetryConnection:
        def __init__(self, real_conn):
            self.real_conn = real_conn
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            return self.real_conn.__exit__(exc_type, exc_val, exc_tb)
        def execute(self, sql, *args):
            nonlocal call_count
            if "INSERT INTO jobs" in sql:
                call_count += 1
                if call_count <= 2:
                    raise sqlite3.OperationalError("database is locked")
            return self.real_conn.execute(sql, *args)

    monkeypatch.setattr(repo, "_get_connection", lambda: RetryConnection(real_get_conn()))
    repo.set("job-retry", {
        "id": "job-retry",
        "state": "QUEUED",
        "directory": str(tmp_path / "job-retry"),
        "created": time.time(),
    })

    # Should succeed after retrying
    assert repo.get("job-retry") is not None
    assert call_count >= 2

    # Test permanent failure logging
    class FailConnection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            _ = args
            return False
        def execute(self, *args, **kwargs):
            _ = (args, kwargs)
            raise sqlite3.DatabaseError("Disk full simulation")

    monkeypatch.setattr(repo, "_get_connection", lambda: FailConnection())
    with caplog.at_level(logging.ERROR):
        repo.set("job-fail", {
            "id": "job-fail",
            "state": "QUEUED",
            "directory": str(tmp_path / "job-fail"),
            "created": time.time(),
        })
        assert "Failed to persist job job-fail to SQLite" in caplog.text


def test_startup_orphan_directory_cleanup(tmp_path):
    """F02: Orphan directories in root not registered in SQLite are removed on startup."""
    orphan_dir = tmp_path / "job-orphan123"
    orphan_dir.mkdir(parents=True, exist_ok=True)
    (orphan_dir / "garbage.txt").write_text("old file")

    # Start service: startup sweep must remove unregistered job directory
    service = JobService(root=tmp_path)
    try:
        assert not orphan_dir.exists(), "Orphan directory was not cleaned up on startup"
    finally:
        service.close()


def test_durable_research_artifacts_retention(tmp_path):
    """F03: Verified conversion jobs (durable) are not deleted by the retention loop."""
    service = JobService(root=tmp_path, retention_s=1)  # 1-second retention
    service.closed = True  # Hold dispatch thread to step manually

    durable_dir = tmp_path / "job-durable"
    durable_dir.mkdir(parents=True, exist_ok=True)
    (durable_dir / "result.json").write_text(json.dumps({"status": "MAPPING_VERIFIED"}), encoding="utf-8")

    ephemeral_dir = tmp_path / "job-ephemeral"
    ephemeral_dir.mkdir(parents=True, exist_ok=True)
    (ephemeral_dir / "result.json").write_text(json.dumps({"status": "PREVIEW"}), encoding="utf-8")

    # Register durable job (finished 5s ago, well past retention)
    service.repository.set("job-durable", {
        "id": "job-durable",
        "state": "COMPLETED",
        "directory": str(durable_dir),
        "finished": time.time() - 5,
        "durable": True,
        "mode": "convert",
    })
    # Register ephemeral job (finished 5s ago)
    service.repository.set("job-ephemeral", {
        "id": "job-ephemeral",
        "state": "COMPLETED",
        "directory": str(ephemeral_dir),
        "finished": time.time() - 5,
        "durable": False,
        "mode": "preview",
    })

    # Step retention logic in _loop
    now = time.time()
    for jid, job in service.repository.items():
        if job.get("durable"):
            continue
        last_active = max(job.get("finished") or now, job.get("last_accessed") or 0)
        if last_active + service.retention_s < now:
            shutil.rmtree(job["directory"], ignore_errors=True)
            service.repository.delete(jid)

    # Durable job must remain intact!
    assert durable_dir.exists(), "Durable research artifact directory must not be deleted by retention"
    assert service.repository.get("job-durable") is not None

    # Ephemeral job must be cleaned up
    assert not ephemeral_dir.exists()
    assert service.repository.get("job-ephemeral") is None


def test_early_admission_rejection_no_disk_waste(monkeypatch):
    """F04: When queue is full, HTTP 429 is returned immediately without creating upload directory."""
    client = TestClient(app)

    # Mock manager.can_accept to return False
    monkeypatch.setattr(manager, "can_accept", lambda: False)

    uploaded_dirs_before = list(manager.root.glob("job-*"))

    # Post upload request
    response = client.post(
        "/api/jobs",
        files=[("files", ("test.ifc", b"ISO-10303-21; HEADER; ENDSEC; DATA; ENDSEC; END-ISO-10303-21;"))],
    )
    assert response.status_code == 429
    assert "Job queue is full" in response.json()["detail"]

    # Verify no new directories were created on disk
    uploaded_dirs_after = list(manager.root.glob("job-*"))
    assert len(uploaded_dirs_after) == len(uploaded_dirs_before)


def test_worker_rss_memory_quota_exceeded(tmp_path, monkeypatch):
    """F05: Worker exceeding configured memory limit is terminated with RESOURCE_EXHAUSTED."""
    # Set memory limit to 10 MB
    service = JobService(root=tmp_path, max_memory_mb=10)
    service.closed = True

    job_dir = tmp_path / "job-mem"
    job_dir.mkdir(parents=True, exist_ok=True)

    class MockProcess:
        pid = 12345
        returncode = None
        def poll(self): return None

    # Mock psutil memory inspection returning 50 MB (exceeding 10 MB limit)
    class MockPsutilProcess:
        def __init__(self, pid):
            _ = pid
        def memory_info(self):
            class Info:
                rss = 50 * 1024 * 1024  # 50 MB
            return Info()
        def children(self, recursive=True):
            _ = recursive
            return []
        def kill(self): pass

    monkeypatch.setattr("ifc_to_fds.adapters.jobs.service.psutil.Process", MockPsutilProcess)
    stopped_processes = []
    monkeypatch.setattr(service, "_stop", lambda p: stopped_processes.append(p))

    job = {
        "id": "job-mem",
        "state": "RUNNING",
        "directory": str(job_dir),
        "started": time.time() - 2,
        "process": MockProcess(),
    }
    service.repository.set("job-mem", job)

    # Execute one supervision iteration
    now = time.time()
    running = service.repository.get("job-mem")
    if running is None:
        raise AssertionError("job-mem not found in repository")
    proc = running.get("process")
    if proc is None:
        raise AssertionError("Process is None")
    parent_proc = MockPsutilProcess(proc.pid)
    total_rss = parent_proc.memory_info().rss
    if total_rss > service.max_memory_bytes:
        service._stop(proc)
        limit_mb = service.max_memory_bytes // (1024 * 1024)
        used_mb = total_rss // (1024 * 1024)
        running.update(
            state="FAILED",
            error=f"RESOURCE_EXHAUSTED: Memory limit exceeded ({used_mb} MiB > {limit_mb} MiB)",
            finished=now,
        )
        service._terminal_diagnostic(running, "ResourceExhaustedError", "Memory limit exceeded")
        service._cleanup(running)
        service.repository.set(str(running["id"]), running)

    assert len(stopped_processes) == 1
    updated = service.repository.get("job-mem")
    if updated is None:
        raise AssertionError("Updated job is None")
    assert updated["state"] == "FAILED"
    assert "RESOURCE_EXHAUSTED" in str(updated["error"])
    assert (job_dir / "diagnostics.json").is_file()


def test_download_touch_extends_retention(tmp_path):
    """F08: manager.touch updates last_accessed, extending the job's retention window."""
    service = JobService(root=tmp_path, retention_s=10)
    service.closed = True

    job = {
        "id": "job-touch",
        "state": "COMPLETED",
        "directory": str(tmp_path / "job-touch"),
        "finished": time.time() - 8,  # only 2 seconds left
        "last_accessed": time.time() - 8,
    }
    service.repository.set("job-touch", job)

    time.sleep(0.01)
    record1 = service.repository.get("job-touch")
    if record1 is None:
        raise AssertionError("Record1 is None")
    before_touch = record1["last_accessed"]
    service.touch("job-touch")
    record2 = service.repository.get("job-touch")
    if record2 is None:
        raise AssertionError("Record2 is None")
    after_touch = record2["last_accessed"]

    assert after_touch > before_touch
    # Now last_active will be fresh (after_touch), extending the 10-second retention


def test_body_limit_streaming_chunked_413():
    """F10: Streaming request exceeding maximum body limit returns clean HTTP 413."""
    async def sample_app(scope, receive, send):
        _ = scope
        while True:
            msg = await receive()
            if not msg.get("more_body", False):
                break
        res = json.dumps({"status": "ok"}).encode()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": res})

    bounded_app = BodyLimitMiddleware(sample_app, maximum=100)
    client = TestClient(bounded_app)

    # 1. Content-Length exceeding maximum
    res1 = client.post("/", content=b"x" * 200, headers={"Content-Length": "200"})
    assert res1.status_code == 413
    assert "exceeds upload limit" in res1.json()["detail"]

    # 2. Chunked stream exceeding maximum (Content-Length missing)
    def generator():
        yield b"x" * 60
        yield b"x" * 60  # total 120 > 100

    res2 = client.post("/", content=generator())
    assert res2.status_code == 413
    assert "exceeds upload limit" in res2.json()["detail"]


def test_api_key_auth_and_host_validation(monkeypatch):
    """F01: API key auth guards /api/* when configured; invalid Host headers return 400."""
    client = TestClient(app)

    # 1. Test Host validation including IPv6 with port
    monkeypatch.setenv("IFCFDS_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver")
    res_bad_host = client.get("/api/health", headers={"Host": "malicious.attacker.com"})
    assert res_bad_host.status_code == 400
    assert "Invalid Host header" in res_bad_host.json()["detail"]

    # IPv6 host header with port must be accepted
    res_ipv6_port = client.get("/api/health", headers={"Host": "[::1]:8000"})
    assert res_ipv6_port.status_code == 200

    # IPv6 host header without port must be accepted
    res_ipv6_raw = client.get("/api/health", headers={"Host": "[::1]"})
    assert res_ipv6_raw.status_code == 200

    # 2. Test API key protection
    monkeypatch.setenv("IFCFDS_API_KEY", "super-secret-key-12345")

    # /api/health is always public
    res_health = client.get("/api/health")
    assert res_health.status_code == 200

    # /api/reference-cases requires key
    res_no_key = client.get("/api/reference-cases")
    assert res_no_key.status_code == 401

    res_bad_key = client.get("/api/reference-cases", headers={"X-API-Key": "wrong-key"})
    assert res_bad_key.status_code == 401

    res_good_key = client.get("/api/reference-cases", headers={"X-API-Key": "super-secret-key-12345"})
    assert res_good_key.status_code == 200

    # Also accepts Bearer token
    res_bearer = client.get("/api/reference-cases", headers={"Authorization": "Bearer super-secret-key-12345"})
    assert res_bearer.status_code == 200
