"""Module composition root for the local queue runtime."""

import os
from pathlib import Path


def local_dependencies(root, repository=None, processes=None, retention=None):
    from .infrastructure.sqlite_repository import JobRepository
    from .infrastructure.worker_process import LocalWorkerProcesses
    from .infrastructure.retention import FilesystemJobRetention
    return (
        repository if repository is not None else JobRepository(root=root),
        processes if processes is not None else LocalWorkerProcesses(),
        retention if retention is not None else FilesystemJobRetention(),
    )


def create_job_manager(**options):
    from .application.service import JobService
    root = Path(options.get('root') or os.environ.get('IFCFDS_JOB_ROOT', str(Path.cwd() / '.jobs'))).resolve()
    repository, processes, retention = local_dependencies(
        root, options.pop('repository', None), options.pop('processes', None), options.pop('retention', None)
    )
    return JobService(**options, repository=repository, processes=processes, retention=retention)
