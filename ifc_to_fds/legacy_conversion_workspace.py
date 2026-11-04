"""Compatibility bridge for direct ConvertVerifiedUseCase() callers.

The composition root injects the storage factory in production. This bridge
preserves the historical no-argument use-case constructor until all external
consumers migrate; it is not the preferred application-layer dependency path.
"""


def create_legacy_workspace(output_directory):
    from ifc_to_fds.adapters.storage.conversion_workspace import (
        LocalConversionWorkspaceFactory,
    )

    return LocalConversionWorkspaceFactory().create(output_directory)
