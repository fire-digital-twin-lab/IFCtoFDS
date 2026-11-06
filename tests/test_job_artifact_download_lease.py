"""Protect FileResponse, streaming, and retention from same-process purge races."""

import asyncio
import json
import shutil
import time
import uuid

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import ArtifactLeaseConflict, JobService
from ifc_to_fds.server import LeasedFileResponse, app, diagnostics, geometry_payload, manager


def completed(jid, directory, finished):
    return {
        "id": jid,
        "state": "COMPLETED",
        "mode": "inventory",
        "directory": str(directory),
        "created": finished - 10,
        "finished": finished,
        "last_accessed": finished,
        "durable": False,
    }


async def deliver(response, abort=False):
    messages = []

    async def send(message):
        messages.append(message)
        if abort and message["type"] == "http.response.body":
            raise asyncio.CancelledError()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/jobs/example/diagnostics",
        "http_version": "1.1",
        "scheme": "http",
        "headers": [],
        "query_string": b"",
        "extensions": {},
    }
    if abort:
        with pytest.raises(asyncio.CancelledError):
            await response(scope, receive, send)
    else:
        await response(scope, receive, send)
    return messages


@pytest.mark.parametrize("abort", [False, True])
def test_diagnostics_response_pins_job_until_asgi_completes(abort):
    jid = "lease-test-" + uuid.uuid4().hex
    directory = manager.root / ("job-" + jid)
    directory.mkdir()
    diagnostic = directory / "diagnostics.json"
    diagnostic.write_text(json.dumps({"name": "Test"}), encoding="utf-8")
    manager.repository.register(jid, completed(jid, directory, time.time() - 500))
    try:
        response = diagnostics(jid)
        assert manager._artifact_leases.get(jid) == 1
        denied = TestClient(app).delete(f"/api/jobs/{jid}", params={"purge": "true"})
        assert denied.status_code == 409, denied.text
        assert JobRepository(root=manager.root).get(jid) is not None
        assert diagnostic.is_file()

        messages = asyncio.run(deliver(response, abort=abort))
        if not abort:
            assert any(m["type"] == "http.response.body" for m in messages)
        assert not manager._artifact_leases.get(jid)
        deleted = TestClient(app).delete(f"/api/jobs/{jid}", params={"purge": "true"})
        assert deleted.status_code == 200, deleted.text
        assert not directory.exists()
    finally:
        manager.release_artifact_lease(jid)
        if manager.repository.contains(jid):
            manager.repository.delete(jid)
        shutil.rmtree(directory, ignore_errors=True)


def test_multiple_leases_block_manual_purge_until_all_finish(tmp_path):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "multi-lease"
    directory = tmp_path / ("job-" + jid)
    directory.mkdir()
    (directory / "evidence.txt").write_text("keep", encoding="utf-8")
    service.repository.register(jid, completed(jid, directory, time.time()))
    try:
        service.acquire_artifact_lease(jid)
        service.acquire_artifact_lease(jid)
        with pytest.raises(ArtifactLeaseConflict):
            service.delete_job(jid, purge=True)
        service.release_artifact_lease(jid)
        with pytest.raises(ArtifactLeaseConflict):
            service.delete_job(jid, purge=True)
        service.release_artifact_lease(jid)
        assert service.delete_job(jid, purge=True)["state"] == "DELETED"
        assert not directory.exists()
    finally:
        service.close()


def test_expired_startup_retention_preserves_download_lease(tmp_path):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "expired-lease"
    directory = tmp_path / ("job-" + jid)
    directory.mkdir()
    (directory / "evidence.txt").write_text("keep", encoding="utf-8")
    service.repository.register(jid, completed(jid, directory, time.time() - 1000))
    try:
        service.acquire_artifact_lease(jid)
        service.cleanup_orphaned_directories(max_age_s=1)
        assert service.repository.contains(jid)
        assert directory.is_dir()
        service.release_artifact_lease(jid)
        service.cleanup_orphaned_directories(max_age_s=1)
        assert not service.repository.contains(jid)
        assert not directory.exists()
    finally:
        service.close()


def test_geometry_access_failure_releases_lease(tmp_path):
    # This fixture has no published geometry; a rejected request must not
    # leave a permanent pin that blocks future retention.
    jid = "lease-geometry-" + uuid.uuid4().hex
    directory = manager.root / ("job-" + jid)
    directory.mkdir()
    manager.repository.register(jid, completed(jid, directory, time.time()))
    job = manager.repository.get(jid)
    job["mode"] = "convert"
    try:
        with pytest.raises(HTTPException) as error:
            geometry_payload(jid, "0" * 64)
        assert error.value.status_code == 404
        assert not manager._artifact_leases.get(jid)
    finally:
        manager.repository.delete(jid)
        shutil.rmtree(directory, ignore_errors=True)


def test_failed_response_constructor_does_not_release_other_reader(monkeypatch):
    """Pre-acquired lease cleanup belongs to the route, not the response too."""
    jid = "lease-init-" + uuid.uuid4().hex
    directory = manager.root / ("job-" + jid)
    directory.mkdir()
    diagnostic = directory / "diagnostics.json"
    diagnostic.write_text("{}", encoding="utf-8")
    manager.repository.register(jid, completed(jid, directory, time.time()))
    try:
        manager.acquire_artifact_lease(jid)  # another active reader
        manager.acquire_artifact_lease(jid)  # caller owns this lease
        def reject_file_response(self, *args, **kwargs):
            raise OSError("Response constructor rejected the file")

        with monkeypatch.context() as patch:
            patch.setattr(FileResponse, "__init__", reject_file_response)
            try:
                with pytest.raises(OSError, match="constructor rejected"):
                    LeasedFileResponse(diagnostic, job_id=jid, lease_acquired=True)
            finally:
                manager.release_artifact_lease(jid)  # caller's finally
        assert manager._artifact_leases.get(jid) == 1
        with pytest.raises(ArtifactLeaseConflict):
            manager.delete_job(jid, purge=True)
        assert diagnostic.is_file()
        manager.release_artifact_lease(jid)
        assert manager.delete_job(jid, purge=True)["state"] == "DELETED"
    finally:
        while manager._artifact_leases.get(jid):
            manager.release_artifact_lease(jid)
        if manager.repository.contains(jid):
            manager.repository.delete(jid)
        shutil.rmtree(directory, ignore_errors=True)
