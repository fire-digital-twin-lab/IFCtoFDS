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

    def get_reference_repository(self):
        from ifc_to_fds.adapters.reference import FilesystemReferenceRepository
        return FilesystemReferenceRepository()

    def get_validation_runner(self):
        from ifc_to_fds.validation.runner import ValidationRunner
        return ValidationRunner()

    def get_save_artifacts_use_case(self):
        from ifc_to_fds.application.use_cases.save_artifacts import SaveArtifactsUseCase
        return SaveArtifactsUseCase(repository=self.get_artifact_repository())

    def get_audit_conversion_use_case(self):
        from ifc_to_fds.application.use_cases.audit_conversion import AuditConversionUseCase
        return AuditConversionUseCase()

    def get_convert_verified_use_case(self):
        from ifc_to_fds.application.use_cases.convert_verified import ConvertVerifiedUseCase
        return ConvertVerifiedUseCase()


def create_container(config: Optional[dict[str, Any]] = None) -> Container:
    """Create and configure application container."""
    return Container(config=config)
