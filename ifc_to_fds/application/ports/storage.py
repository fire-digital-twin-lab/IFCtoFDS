"""ArtifactRepository port definition."""

from pathlib import Path
from typing import Any, Dict, Protocol, Union, runtime_checkable


@runtime_checkable
class ArtifactRepositoryPort(Protocol):
    """Port for persisting conversion artifacts, evidence files, and checksums."""

    def save_run_artifacts(
        self, result: Dict[str, Any], output: Union[str, Path]
    ) -> Dict[str, str]:
        ...

    def read_artifact(self, path: Union[str, Path]) -> bytes:
        ...
