"""HTTP component contracts without opening sockets or starting job subprocesses."""

import asyncio
import json
from pathlib import Path
from threading import RLock
from tempfile import SpooledTemporaryFile

import pytest
from fastapi import HTTPException, UploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse

from ifc_to_fds.interfaces.http.routes import create_router
from ifc_to_fds.interfaces.http.security import security_guard


def ready(coroutine):
    """Drive an entirely in-memory coroutine; fail if it needs asynchronous I/O."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coroutine.close()
    raise AssertionError("This component requires an event loop; use a transport integration test")


def request(path, method="GET", **headers):
    return Request({
        "type": "http", "method": method, "scheme": "http", "path": path,
        "query_string": b"", "server": ("testserver", 80),
        "headers": [(b"host", b"testserver"), *[(key.replace("_", "-").encode(), value.encode()) for key, value in headers.items()]],
    })


async def ok(_):
    return JSONResponse({"ok": True})


def memory_file(content):
    stream = SpooledTemporaryFile(max_size=1024)
    stream.write(content)
    stream.seek(0)
    return stream


def test_security_guard_authentication_and_origin_contract(monkeypatch):
    monkeypatch.setenv("IFCFDS_API_KEY", "fixture-key")
    monkeypatch.setenv("IFCFDS_ALLOWED_HOSTS", "testserver")
    monkeypatch.delenv("IFCFDS_ALLOWED_ORIGINS", raising=False)
    assert ready(security_guard(request("/api/health"), ok)).status_code == 200
    assert ready(security_guard(request("/api/jobs"), ok)).status_code == 401
    assert ready(security_guard(request("/api/jobs", authorization="Bearer fixture-key"), ok)).status_code == 200
    assert ready(security_guard(request("/api/jobs", "POST", x_api_key="fixture-key", origin="https://other.example"), ok)).status_code == 403
    assert ready(security_guard(request("/api/jobs", "POST", x_api_key="fixture-key", origin="http://testserver"), ok)).status_code == 200
    invalid = Request({"type": "http", "method": "GET", "scheme": "http", "path": "/api/health", "headers": [(b"host", b"other.example")]})
    assert ready(security_guard(invalid, ok)).status_code == 400


class Manager:
    def __init__(self, root):
        self.root = root
        self.lock = RLock()
        self.jobs = {}
        self.touched = []

    def can_accept(self):
        return True

    def touch(self, jid):
        self.touched.append(jid)


def test_upload_names_and_limits_cleanup(tmp_path):
    router = create_router(Manager(tmp_path), lambda: (4, 8))
    upload = UploadFile(memory_file(b"IFC"), filename="folder/original.ifc")
    directory, paths = ready(router.store_uploads([upload]))
    assert paths[0].read_bytes() == b"IFC"
    assert json.loads((directory / "upload-names.json").read_text()) == {"source-0.ifc": "original.ifc"}
    assert upload.file.closed
    oversized = UploadFile(memory_file(b"12345"), filename="large.ifc")
    with pytest.raises(HTTPException) as error:
        ready(router.store_uploads([oversized]))
    assert error.value.status_code == 413
    assert oversized.file.closed
    assert set(tmp_path.iterdir()) == {directory}, "Failed upload left a staging directory"


def test_cancelled_upload_removes_partial_directory_and_closes_file(tmp_path):
    class CancelledUpload(UploadFile):
        async def read(self, size=-1):
            raise asyncio.CancelledError()

    router = create_router(Manager(tmp_path), lambda: (4, 8))
    upload = CancelledUpload(memory_file(b"IFC"), filename="source.ifc")
    with pytest.raises(asyncio.CancelledError):
        ready(router.store_uploads([upload]))
    assert not list(tmp_path.iterdir())
    assert upload.file.closed


def endpoint(router, path, method):
    return next(route.endpoint for route in router.routes if route.path == path and method in route.methods)


def test_queue_full_rejects_before_spooling(tmp_path):
    manager = Manager(tmp_path)
    manager.can_accept = lambda: False
    router = create_router(manager, lambda: (4, 8))
    upload = UploadFile(memory_file(b"IFC"), filename="source.ifc")
    with pytest.raises(HTTPException) as error:
        ready(endpoint(router, "/api/jobs", "POST")([upload], "{}"))
    assert error.value.status_code == 429
    assert not list(tmp_path.iterdir())
    upload.file.close()


def test_failed_job_has_only_explicitly_unaccepted_checkpoint_download(tmp_path):
    manager = Manager(tmp_path)
    manager.jobs["fixture"] = {"state": "FAILED", "directory": str(tmp_path)}
    (tmp_path / "model.fds").write_text("&HEAD CHID='fixture' /", encoding="utf-8")
    router = create_router(manager, lambda: (4, 8))
    with pytest.raises(HTTPException) as error:
        endpoint(router, "/api/jobs/{jid}/artifacts/{artifact}", "GET")("fixture", "fds")
    assert error.value.status_code == 409
    response = endpoint(router, "/api/jobs/{jid}/checkpoints/{artifact}", "GET")("fixture", "fds")
    assert Path(response.path) == tmp_path / "model.fds"
    assert response.headers["X-Verification-Status"] == "UNACCEPTED-AUDIT_INCOMPLETE-DO_NOT_USE_AS_VERIFIED_OUTPUT"
    assert manager.touched == ["fixture"]
