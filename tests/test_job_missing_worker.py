"""P1 regression: missing process handles must not terminate scheduler supervision."""

import json
import time

from ifc_to_fds.adapters.jobs.repository import JobRepository
from ifc_to_fds.adapters.jobs.service import JobService


class OneIterationWake:
    """Stop a synchronous scheduler loop after its first complete iteration."""

    def __init__(self, service):
        self.service = service

    def clear(self):
        pass

    def set(self):
        pass

    def wait(self, _timeout):
        self.service.closed = True


def test_scheduler_marks_running_job_without_process_failed_and_keeps_loop_alive(
    tmp_path,
):
    service = JobService(root=tmp_path, retention_s=3600)
    jid = "missing-process"
    directory = tmp_path / ("job-" + jid)
    directory.mkdir()
    now = time.time()
    service.repository.register(
        jid,
        {
            "id": jid,
            "state": "RUNNING",
            "directory": str(directory),
            "mode": "inventory",
            "created": now,
            "started": now,
            "finished": None,
            "last_accessed": now,
            "process": None,
        },
    )
    service.wake = OneIterationWake(service)
    try:
        service._loop()
        after = service.repository.get(jid)
        assert after["state"] == "FAILED"
        assert "no worker handle" in after["error"]
        durable = JobRepository(root=tmp_path).get(jid)
        assert durable["state"] == "FAILED"
        diagnostic = json.loads(
            (directory / "diagnostics.json").read_text(encoding="utf-8")
        )
        assert diagnostic["name"] == "WorkerProcessMissingError"
    finally:
        service.close()
