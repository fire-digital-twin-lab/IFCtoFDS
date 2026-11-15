"""Backup/restore drill on a real finished conversion (plan M5.3): the restored store serves the same result."""

import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path

from ifc_to_fds.adapters.jobs.service import JobService
from ifc_to_fds.operations.offline_backup import create_offline_backup, restore_offline_backup

TINY = Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc"


def digest(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.is_file()}


def test_a_completed_job_survives_backup_and_restore_with_identical_artifacts(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("d")  # short root: artifact paths must stay under Windows MAX_PATH
    source = JobService(root=tmp_path / "live")
    directory = source.root / ("job-" + uuid.uuid4().hex)
    directory.mkdir()
    shutil.copy(TINY, directory / "source-0.ifc")
    jid = source.submit([directory / "source-0.ifc"], {}, directory)["id"]
    deadline = time.monotonic() + 120
    while source.snapshot(jid)["state"] not in ("COMPLETED", "FAILED", "TIMED_OUT") and time.monotonic() < deadline:
        time.sleep(0.2)
    assert source.snapshot(jid)["state"] == "COMPLETED", source.snapshot(jid).get("error")
    before = json.dumps(source.result(jid), sort_keys=True)
    files_before = digest(directory)
    source.close()  # the runbook requires the API and workers to be stopped

    backup = tmp_path / "backup"
    assert create_offline_backup(source.root, backup)["job_count"] == 1
    restored_root = tmp_path / "restored"
    assert restore_offline_backup(backup, restored_root)["verified"] is True

    restored = JobService(root=restored_root)
    try:
        assert restored.snapshot(jid)["state"] == "COMPLETED"
        assert json.dumps(restored.result(jid), sort_keys=True).replace(str(restored_root), "ROOT") == \
            before.replace(str(source.root), "ROOT")
        assert digest(restored_root / directory.name) == files_before
    finally:
        restored.close()
