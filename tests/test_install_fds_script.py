"""Regression tests for the checksum-pinned FDS downloader."""

from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import urllib.error

import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install-fds.py"


def _load_installer():
    spec = importlib.util.spec_from_file_location("ifctofds_install_fds", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_download_retries_transient_http_504_and_keeps_checksum_pin(
    tmp_path,
    monkeypatch,
):
    module = _load_installer()
    payload = b"pinned-fds-test-payload"
    monkeypatch.setattr(module, "ARCHIVE_SHA", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(module, "RETRY_DELAYS_S", (0.0, 0.0))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    attempts = 0

    def fake_urlopen(request, timeout):
        nonlocal attempts
        attempts += 1
        assert timeout == module.DOWNLOAD_TIMEOUT_S
        if attempts < 3:
            raise urllib.error.HTTPError(
                module.URL,
                504,
                "Gateway Time-out",
                {},
                None,
            )
        return io.BytesIO(payload)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    archive = tmp_path / "fds.exe"

    module._download_archive(archive)

    assert attempts == 3
    assert archive.read_bytes() == payload
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == module.ARCHIVE_SHA
    assert not (tmp_path / "fds.exe.part").exists()


def test_download_does_not_retry_nontransient_http_error(tmp_path, monkeypatch):
    module = _load_installer()
    monkeypatch.setattr(module, "RETRY_DELAYS_S", (0.0, 0.0))
    attempts = 0

    def fake_urlopen(request, timeout):
        nonlocal attempts
        attempts += 1
        raise urllib.error.HTTPError(
            module.URL,
            404,
            "Not Found",
            {},
            None,
        )

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        module._download_archive(tmp_path / "fds.exe")

    assert exc_info.value.code == 404
    assert attempts == 1


def test_download_rejects_checksum_mismatch_without_promoting_artifact(
    tmp_path,
    monkeypatch,
):
    module = _load_installer()
    monkeypatch.setattr(module, "ARCHIVE_SHA", "0" * 64)
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda request, timeout: io.BytesIO(b"unexpected"),
    )
    archive = tmp_path / "fds.exe"

    with pytest.raises(ValueError, match="pinned checksum"):
        module._download_archive(archive)

    assert not archive.exists()
    assert not (tmp_path / "fds.exe.part").exists()
