"""Public API of the jobs module; only named exports are supported."""

from ifc_to_fds.modules._exports import resolve


_EXPORTS = {'create_job_manager': ('ifc_to_fds.modules.jobs.factory', 'create_job_manager'),
 'JobManager': ('ifc_to_fds.modules.jobs.application.service', 'JobService'),
 'JobRepository': ('ifc_to_fds.modules.jobs.infrastructure.sqlite_repository', 'JobRepository'),
 'JobService': ('ifc_to_fds.modules.jobs.application.service', 'JobService')}

__all__ = list(_EXPORTS)


def __getattr__(name):
    return resolve(_EXPORTS, name)
