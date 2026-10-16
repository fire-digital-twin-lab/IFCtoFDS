"""SaveArtifacts use case: persists conversion and validation artifacts to storage."""

from pathlib import Path
from typing import Any, Dict, Optional, Union
from ifc_to_fds.application.ports.storage import ArtifactRepositoryPort


class SaveArtifactsUseCase:
    """Persists all conversion artifacts, checksums, and geometry packages."""

    def __init__(self, repository: Optional[ArtifactRepositoryPort] = None):
        self._repository = repository

    @property
    def repository(self) -> ArtifactRepositoryPort:
        if self._repository is None:
            from ifc_to_fds.bootstrap.container import get_default_artifact_repository
            self._repository = get_default_artifact_repository()
        return self._repository

    def execute(self, result: Dict[str, Any], output: Union[str, Path]) -> Dict[str, str]:
        return self.repository.save_run_artifacts(result=result, output=output)
