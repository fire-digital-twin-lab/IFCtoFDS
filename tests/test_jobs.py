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
