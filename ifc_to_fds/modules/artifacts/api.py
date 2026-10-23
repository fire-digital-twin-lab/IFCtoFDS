"""Public API of the artifacts module; only named exports are supported."""

from ifc_to_fds.modules._exports import resolve

_EXPORTS = {'LocalConversionWorkspaces': ('ifc_to_fds.modules.artifacts.infrastructure.conversion_workspace',
                               'LocalConversionWorkspaces'),
 'verify_run_artifacts': ('ifc_to_fds.modules.artifacts.infrastructure.filesystem_repository', 'verify_run_artifacts'),
 'LocalFilesystemArtifactRepository': ('ifc_to_fds.modules.artifacts.infrastructure.filesystem_repository',
                                       'LocalFilesystemArtifactRepository')}

__all__ = list(_EXPORTS)


def __getattr__(name):
    return resolve(_EXPORTS, name)
