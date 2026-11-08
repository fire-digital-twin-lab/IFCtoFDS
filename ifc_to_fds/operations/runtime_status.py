"""Operational telemetry for staging/production supervision.

This module reports software/runtime state only. It is not a scientific verdict,
a CFD validation result, or a substitute for external monitoring and alerting.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import shutil
import time
from typing import Any

import psutil

from ifc_to_fds.adapters.jobs.readiness import is_scheduler_healthy


_TERMINAL_STATES = ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT")


def collect_operational_status(service: Any, *, now: float | None = None) -> dict[str, Any]:
    """Collect bounded, path-free telemetry from a JobService-like object."""

    timestamp = time.time() if now is None else now
    with service.lock:
        jobs = list(service.repository.all_jobs())
        states = Counter(str(job.get("state", "UNKNOWN")) for job in jobs)
        scheduler_healthy = is_scheduler_healthy(service)
        accepting_jobs = (
            bool(service.can_accept()) and not service.closed and scheduler_healthy
        )
        uptime_s = max(0.0, timestamp - float(service.boot_time))
        max_waiting = int(service.max_waiting)

    process = psutil.Process()
    rss_bytes = int(process.memory_info().rss)

    disk_ok = True
    disk_total_bytes: int | None
    disk_free_bytes: int | None
    try:
        usage = shutil.disk_usage(Path(service.root))
        disk_total_bytes = int(usage.total)
        disk_free_bytes = int(usage.free)
    except OSError:
        disk_ok = False
        disk_total_bytes = None
        disk_free_bytes = None

    pending = states["QUEUED"] + states["RUNNING"]
    terminal = sum(states[state] for state in _TERMINAL_STATES)
    operational = scheduler_healthy and disk_ok and not service.closed

    return {
        "status": "ok" if operational else "degraded",
        "scheduler_healthy": scheduler_healthy,
        "accepting_jobs": accepting_jobs,
        "service_closed": bool(service.closed),
        "uptime_s": round(uptime_s, 3),
        "jobs": {
            "total": len(jobs),
            "pending": pending,
            "terminal": terminal,
            "states": dict(sorted(states.items())),
            "max_waiting": max_waiting,
        },
        "process": {"rss_bytes": rss_bytes},
        "storage": {
            "probe_ok": disk_ok,
            "total_bytes": disk_total_bytes,
            "free_bytes": disk_free_bytes,
        },
    }
