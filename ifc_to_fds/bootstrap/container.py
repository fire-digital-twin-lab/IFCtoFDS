"""Application dependency injection and bootstrap container."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Container:
    """Composition root assembling ports, adapters, and application use cases."""

    config: Optional[dict[str, Any]] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}

    def get_artifact_repository(self):
        from ifc_to_fds.adapters.storage.filesystem import LocalFilesystemArtifactRepository
        return LocalFilesystemArtifactRepository()


_default_container = Container()


def get_default_artifact_repository():
    return _default_container.get_artifact_repository()


def create_container(config: Optional[dict[str, Any]] = None) -> Container:
    """Create and configure application container."""
    return Container(config=config)
