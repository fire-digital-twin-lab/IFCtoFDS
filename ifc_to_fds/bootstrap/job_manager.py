"""Lazy job service: no filesystem or background work during application import."""

import os
from threading import Lock


class LazyJobManager:
    def __init__(self):
        object.__setattr__(self, "_instance", None)
        object.__setattr__(self, "_lock", Lock())

    def _get(self):
        with self._lock:
            if self._instance is None:
                from ifc_to_fds.modules.jobs.api import create_job_manager

                object.__setattr__(self, "_instance", create_job_manager(
                    max_waiting=int(os.getenv("IFCFDS_MAX_WAITING", "2")),
                    timeout_s=int(os.getenv("IFCFDS_TIMEOUT_S", "1800")),
                ))
            return self._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._get(), name, value)

    def close(self):
        with self._lock:
            if self._instance is not None:
                self._instance.close()
