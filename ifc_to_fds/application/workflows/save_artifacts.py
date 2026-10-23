"""SaveArtifacts use case: persists conversion and validation artifacts to storage."""

from pathlib import Path
from typing import Any, Dict, Union
from ifc_to_fds.application.ports.storage import ArtifactRepositoryPort


class SaveArtifactsUseCase:
    """Persists all conversion artifacts, checksums, and geometry packages."""

    def __init__(self, repository: ArtifactRepositoryPort):
        self.repository = repository

    def execute(self, result: Dict[str, Any], output: Union[str, Path]) -> Dict[str, str]:
        return self.repository.save_run_artifacts(result=result, output=output)

