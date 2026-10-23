"""Bounded local job queue using killable child processes and disk artifacts (Compatibility Facade).

Re-exports from ifc_to_fds.adapters.jobs:
  - JobService (JobManager)
  - WorkerRunner (run_worker)
  - JobRepository
"""

import subprocess
import sys
from ifc_to_fds.modules.jobs.api import JobManager, JobRepository, JobService
from ifc_to_fds.interfaces.worker.runner import WorkerRunner

__all__ = [
    "JobManager",
    "JobService",
    "JobRepository",
    "WorkerRunner",
    "run_worker",
]


def run_worker(directory):
    return WorkerRunner.run(directory)


if __name__ == "__main__":
    sys.exit(run_worker(sys.argv[1]))
