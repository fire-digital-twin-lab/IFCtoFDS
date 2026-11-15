"""Upload admission, orphan cleanup, durable retention and the verified-evidence cache."""

import hashlib
import json
import os
import threading
import time

import pytest
from fastapi.testclient import TestClient

from ifc_to_fds.adapters.jobs import evidence_index
from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService
from ifc_to_fds.server import app, manager

client = TestClient(app, raise_server_exceptions=False)


def _job_dirs():
    return {p.name for p in manager.root.glob("job-*")}


@pytest.mark.parametrize(
    "url,field",
    [("/api/jobs", "files"), ("/api/preview-jobs", "file"), ("/api/inventory", "file"), ("/api/convert", "file")],
)
def test_unexpected_submit_error_leaves_no_orphan_directory(tiny_ifc, monkeypatch, url, field):
    path, _, _ = tiny_ifc
    before = _job_dirs()

    def disk_full(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(manager, "submit", disk_full)
    response = client.post(url, files={field: ("tiny.ifc", path.read_bytes())})
    assert response.status_code == 500
    assert _job_dirs() == before


def test_reserved_slots_reject_parallel_uploads_before_any_byte_is_written(tiny_ifc):
    path, _, _ = tiny_ifc
    before = _job_dirs()
    held = 0
    try:
        for _ in range(manager.max_waiting + 5):  # bounded: a broken limit must fail, not hang
            try:
                manager.reserve_upload()
            except OverflowError:
                break
            held += 1
        assert held <= manager.max_waiting + 1
        response = client.post("/api/jobs", files={"files": ("tiny.ifc", path.read_bytes())})
        assert response.status_code == 429
        assert _job_dirs() == before
    finally:
        for _ in range(held):
            manager.release_upload()
    assert manager._uploads == 0


def test_release_frees_the_slot(tmp_path):
    service = JobService(root=tmp_path, max_waiting=1)
    try:
        service.reserve_upload()
        service.reserve_upload()  # max_waiting + 1 running slot
        with pytest.raises(OverflowError):
            service.reserve_upload()
        service.release_upload()
        service.reserve_upload()
    finally:
        service.close()


def _job(directory, jid, *, finished, durable, accessed=None):
    return {
        "id": jid, "state": "COMPLETED", "directory": str(directory), "mode": "convert",
        "created": finished - 100, "started": finished - 90, "finished": finished,
        "last_accessed": finished if accessed is None else accessed,
        "durable": durable, "retention_s": 60, "process": None,
    }


def _seed(repository_root, jid, *, finished, durable, accessed=None, register=None):
    directory = repository_root / f"job-{jid}"
    directory.mkdir()
    (directory / "result.json").write_text("{}", encoding="utf-8")
    job = _job(directory, jid, finished=finished, durable=durable, accessed=accessed)
    (register or JobRepository(root=repository_root)).register(jid, job)
    return directory


def test_durable_job_expires_after_the_durable_window_but_not_before(tmp_path):
    now = time.time()
    old = _seed(tmp_path, "old", finished=now - 40 * 86400, durable=True)
    recent = _seed(tmp_path, "recent", finished=now - 3 * 86400, durable=True)
    service = JobService(root=tmp_path, retention_s=60, durable_retention_s=30 * 86400)
    try:
        assert not old.exists()
        assert recent.is_dir()
        assert JobRepository(root=tmp_path).get("recent") is not None
    finally:
        service.close()


def test_durable_retention_zero_keeps_verified_jobs_forever(tmp_path):
    old = _seed(tmp_path, "old", finished=time.time() - 400 * 86400, durable=True)
    service = JobService(root=tmp_path, retention_s=60, durable_retention_s=0)
    try:
        assert old.is_dir()
    finally:
        service.close()


def test_live_sweep_removes_an_expired_durable_job(tmp_path):
    service = JobService(root=tmp_path, retention_s=60, durable_retention_s=100)
    try:
        now = time.time()
        directory = _seed(tmp_path, "live", finished=now - 500, durable=True, register=service.repository)
        threading.Thread(target=service._loop, daemon=True).start()
        deadline = time.time() + 10
        while directory.exists() and time.time() < deadline:
            time.sleep(0.1)
        assert not directory.exists()
    finally:
        service.close()


def test_touch_skips_the_commit_when_the_job_was_just_accessed(tmp_path):
    service = JobService(root=tmp_path, retention_s=3600)
    try:
        now = time.time()
        _seed(tmp_path, "fresh", finished=now - 5, durable=False, accessed=now - 1, register=service.repository)
        _seed(tmp_path, "stale", finished=now - 500, durable=False, accessed=now - 120, register=service.repository)
        calls = []
        original = service.repository.set_durable
        service.repository.set_durable = lambda *a, **k: calls.append(a[0]) or original(*a, **k)
        service.touch("fresh")
        service.touch("stale")
        assert calls == ["stale"]
    finally:
        service.close()


@pytest.fixture
def scenario_job(tmp_path):
    evidence_index._VERIFIED.clear()
    directory = tmp_path / "job"
    directory.mkdir()
    fds = b"&HEAD CHID='x' /\n"
    (directory / "scenario.fds").write_bytes(fds)
    result = {"artifacts": {}, "evidence": {"fds_sha256": hashlib.sha256(fds).hexdigest()}}
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")
    evidence_index.write_evidence_index(directory, "scenario", result)
    return directory, result


def _age(directory, seconds=30):
    stamp = time.time() - seconds
    for path in directory.iterdir():
        os.utime(path, (stamp, stamp))


def _count_hashes(monkeypatch):
    calls = []
    original = evidence_index._sha256
    monkeypatch.setattr(evidence_index, "_sha256", lambda path: calls.append(path.name) or original(path))
    return calls


def test_settled_evidence_is_hashed_once_across_repeated_verifications(scenario_job, monkeypatch):
    directory, result = scenario_job
    _age(directory)
    calls = _count_hashes(monkeypatch)
    for _ in range(5):
        evidence_index.verify_evidence_index(directory, "scenario", result)
    assert sorted(calls) == ["result.json", "scenario.fds"]


def test_cached_verification_still_catches_a_changed_file(scenario_job, monkeypatch):
    directory, result = scenario_job
    _age(directory)
    evidence_index.verify_evidence_index(directory, "scenario", result)
    (directory / "scenario.fds").write_bytes(b"&HEAD CHID='y' /\n")  # same size, new mtime
    _age(directory, 10)
    with pytest.raises(ValueError, match="changed or missing"):
        evidence_index.verify_evidence_index(directory, "scenario", result)


def test_fresh_files_are_never_trusted_from_the_cache(scenario_job, monkeypatch):
    directory, result = scenario_job  # just written: inside the two-second settle window
    calls = _count_hashes(monkeypatch)
    evidence_index.verify_evidence_index(directory, "scenario", result)
    evidence_index.verify_evidence_index(directory, "scenario", result)
    assert len(calls) == 4
