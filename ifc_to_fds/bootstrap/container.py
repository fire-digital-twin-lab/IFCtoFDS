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
        from ifc_to_fds.modules.artifacts.api import LocalFilesystemArtifactRepository
        return LocalFilesystemArtifactRepository()

    def get_reference_repository(self):
        from ifc_to_fds.modules.reference.api import FilesystemReferenceRepository
        return FilesystemReferenceRepository()

    def get_validation_runner(self):
        from ifc_to_fds.modules.verification.api import ValidationRunner
        return ValidationRunner()

    def get_save_artifacts_use_case(self):
        from ifc_to_fds.application.workflows.save_artifacts import SaveArtifactsUseCase
        return SaveArtifactsUseCase(repository=self.get_artifact_repository())

    def get_audit_conversion_use_case(self):
        from ifc_to_fds.application.workflows.audit_conversion import AuditConversionUseCase
        from ifc_to_fds.modules.verification.api import IndependentValidationEngine

        return AuditConversionUseCase(
            model_preparer=self.get_model_preparer(),
            validation_engine=IndependentValidationEngine(),
            reference_reader=self.get_reference_reader(),
        )

    def get_reference_reader(self):
        from ifc_to_fds.modules.reference.api import inspect_case
        return inspect_case

    def get_model_preparer(self):
        from ifc_to_fds.application.workflows.prepare_model import ModelPreparer
        from ifc_to_fds.modules.bim.api import IfcOpenShellReader

        return ModelPreparer(IfcOpenShellReader())

    def get_convert_verified_use_case(self):
        from ifc_to_fds.application.workflows.convert_verified import ConvertVerifiedUseCase
        from ifc_to_fds.modules.fds.api import FdsExporter
        from ifc_to_fds.modules.artifacts.api import LocalConversionWorkspaces

        return ConvertVerifiedUseCase(
            model_preparer=self.get_model_preparer(),
            exporter=FdsExporter(),
            workspaces=LocalConversionWorkspaces(),
            audit_use_case=self.get_audit_conversion_use_case(),
        )


def create_container(config: Optional[dict[str, Any]] = None) -> Container:
    """Create and configure application container."""
    return Container(config=config)
