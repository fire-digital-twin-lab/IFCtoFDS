"""Regression tests for production-safe operational telemetry."""

from __future__ import annotations

import threading
from types import SimpleNamespace

from ifc_to_fds.operations.runtime_status import collect_operational_status


class _Repository:
    def __init__(self, jobs):
        self._jobs = jobs

    def all_jobs(self):
        return list(self._jobs)

    def count_pending(self):
        return sum(j["state"] in ("QUEUED", "RUNNING") for j in self._jobs)


class _Service:
    def __init__(self, root, jobs):
        self.lock = threading.RLock()
        self.repository = _Repository(jobs)
        self.closed = False
        self.thread = None
        self.boot_time = 100.0
        self.max_waiting = 2
        self.root = root

    def can_accept(self):
        return self.repository.count_pending() < self.max_waiting + 1


def test_operational_status_reports_bounded_runtime_metrics(tmp_path):
    service = _Service(
        tmp_path,
        [
            {"state": "QUEUED"},
            {"state": "RUNNING"},
            {"state": "COMPLETED"},
            {"state": "FAILED"},
        ],
    )

    result = collect_operational_status(service, now=160.0)

    assert result["status"] == "ok"
    assert result["scheduler_healthy"] is False  # pending work needs a live supervisor
    assert result["jobs"]["total"] == 4
    assert result["jobs"]["pending"] == 2
    assert result["jobs"]["terminal"] == 2
    assert result["jobs"]["states"] == {
        "COMPLETED": 1,
        "FAILED": 1,
        "QUEUED": 1,
        "RUNNING": 1,
    }
    assert result["uptime_s"] == 60.0
    assert result["process"]["rss_bytes"] > 0
    assert result["storage"]["probe_ok"] is True
    assert result["storage"]["free_bytes"] >= 0
    assert "root" not in result["storage"]


def test_idle_service_without_supervisor_is_healthy(tmp_path):
    service = _Service(tmp_path, [])

    result = collect_operational_status(service, now=101.0)

    assert result["status"] == "ok"
    assert result["scheduler_healthy"] is True
    assert result["accepting_jobs"] is True


def test_closed_service_is_degraded(tmp_path):
    service = _Service(tmp_path, [])
    service.closed = True

    result = collect_operational_status(service, now=101.0)

    assert result["status"] == "degraded"
    assert result["service_closed"] is True
    assert result["accepting_jobs"] is False
