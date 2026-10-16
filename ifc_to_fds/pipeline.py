"""One conversion/audit service for CLI, HTTP and background jobs (Compatibility Facade).

Orchestrates calls to application use cases:
  - ConvertVerifiedUseCase
  - AuditConversionUseCase
  - SaveArtifactsUseCase
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from ifc_to_fds.application.dto import validate_configuration
from ifc_to_fds.application.use_cases import (
    AuditConversionUseCase,
    ConvertVerifiedUseCase,
    SaveArtifactsUseCase,
    prepare_model,
)
from ifc_to_fds.core.canonical import CanonicalModel
from ifc_to_fds.mapping.manifest import MappingManifest
from ifc_to_fds.validation.acceptance import AcceptanceReport

__all__ = [
    "validate_configuration",
    "prepare",
    "audit",
    "convert",
    "save_artifacts",
]


def prepare(
    paths: list[str],
    configuration: Dict[str, Any],
    reference: bool = False,
) -> CanonicalModel:
    """Prepares canonical model (Compatibility Facade)."""
    return prepare_model(paths, configuration, reference=reference)


def audit(
    paths: list[str],
    fds_text: str,
    manifest: MappingManifest,
    configuration: Optional[Dict[str, Any]] = None,
    geometry_package: Optional[Dict[str, Any]] = None,
) -> Tuple[CanonicalModel, MappingManifest, AcceptanceReport]:
    """Independent audit of serialized FDS against source IFC (Compatibility Facade)."""
    return AuditConversionUseCase().execute(
        paths=paths,
        fds_text=fds_text,
        manifest=manifest,
        configuration=configuration,
        geometry_package=geometry_package,
    )


def convert(
    paths: list[str],
    configuration: Optional[Dict[str, Any]] = None,
    output_directory: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Converts IFC models to FDS with verification (Compatibility Facade)."""
    return ConvertVerifiedUseCase().execute(
        paths=paths,
        configuration=configuration,
        output_directory=output_directory,
    )


def save_artifacts(
    result: Dict[str, Any],
    output: Union[str, Path],
) -> Dict[str, str]:
    """Persists artifacts to disk (Compatibility Facade)."""
    return SaveArtifactsUseCase().execute(result=result, output=output)
