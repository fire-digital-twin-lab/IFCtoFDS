import os
import subprocess
import sys
import time
import pytest
from ifc_to_fds.jobs import JobManager


def test_queue_cancel_and_cleanup(tmp_path, monkeypatch):
    manager = JobManager(root=tmp_path, max_waiting=0)
    manager.closed = True  # Hold dispatch to test the actual pending capacity.
    directory = tmp_path / "one"
    directory.mkdir()
    source = directory / "source-0.ifc"
    source.write_text("fixture", encoding="utf-8")
    job = manager.submit([source], {}, directory)
    with pytest.raises(OverflowError):
        manager.submit([source], {}, directory)
    assert manager.cancel(job["id"])["state"] == "CANCELLED"
    assert not source.exists()
    with pytest.raises(ValueError):
        manager.result(job["id"])


@pytest.mark.parametrize("action", ["cancel", "timeout"])
def test_running_worker_is_killed(tmp_path, monkeypatch, action):
    real_popen = subprocess.Popen

    def sleeping_worker(*args, **kwargs):
        return real_popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    monkeypatch.setattr("ifc_to_fds.jobs.subprocess.Popen", sleeping_worker)
    manager = JobManager(root=tmp_path, timeout_s=0.25 if action == "timeout" else 30)
    directory = tmp_path / "job"
    directory.mkdir()
    source = directory / "source-0.ifc"
    source.write_text("fixture", encoding="utf-8")
    try:
        job = manager.submit([source], {}, directory)
        deadline = time.monotonic() + 10
        while (
            manager.snapshot(job["id"])["state"] == "QUEUED"
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        process = manager.jobs[job["id"]]["process"]
        assert process is not None
        if action == "cancel":
            manager.cancel(job["id"])
        else:
            while (
                manager.snapshot(job["id"])["state"] == "RUNNING"
                and time.monotonic() < deadline
            ):
                time.sleep(0.02)
        assert manager.snapshot(job["id"])["state"] == (
            "CANCELLED" if action == "cancel" else "TIMED_OUT"
        )
        assert process.poll() is not None
        assert not source.exists()
    finally:
        manager.close()


def test_worker_environment_strips_api_key(tmp_path, monkeypatch):
    """M-6: ensure worker environment does not inherit IFCFDS_API_KEY from host process."""
    captured_env = {}

    def mock_popen(cmd, *args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        return subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.exit(0)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    monkeypatch.setenv("IFCFDS_API_KEY", "super_secret_test_key_123")
    monkeypatch.setattr("ifc_to_fds.jobs.subprocess.Popen", mock_popen)
    manager = JobManager(root=tmp_path)
    directory = tmp_path / "job_key_test"
    directory.mkdir()
    source = directory / "source-0.ifc"
    source.write_text("dummy", encoding="utf-8")
    try:
        job = manager.submit([source], {}, directory)
        deadline = time.monotonic() + 5
        while manager.snapshot(job["id"])["state"] == "QUEUED" and time.monotonic() < deadline:
            time.sleep(0.02)
        assert "IFCFDS_API_KEY" not in captured_env
    finally:
        manager.close()


def test_cli_serve_with_api_key_file(tmp_path, monkeypatch):
    """M-6: ensure CLI serve loads API key from --api-key-file."""
    from ifc_to_fds.cli import main as cli_main

    key_file = tmp_path / "secret.key"
    key_file.write_text("my-file-api-key\n", encoding="utf-8")

    uvicorn_called = False

    def mock_run(app_str, host, port):
        nonlocal uvicorn_called
        uvicorn_called = True
        assert os.environ.get("IFCFDS_API_KEY") == "my-file-api-key"

    monkeypatch.setattr("uvicorn.run", mock_run)
    try:
        exit_code = cli_main(["serve", "--host", "0.0.0.0", "--port", "8000", "--api-key-file", str(key_file)])
        assert exit_code == 0
        assert uvicorn_called
    finally:
        os.environ.pop("IFCFDS_API_KEY", None)

