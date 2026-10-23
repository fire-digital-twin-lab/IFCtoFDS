"""Abstract output port for reference repository storage."""

from pathlib import Path
from typing import Any, Dict, Protocol, Tuple, Union, runtime_checkable


@runtime_checkable
class ReferenceRepositoryPort(Protocol):
    """Port for reading, verifying, and hashing golden reference bundles."""

    def bundle_digest(self, directory: Union[str, Path]) -> str:
        ...

    def inspect_case(
        self, directory: Union[str, Path]
    ) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        ...

    def resolve_sources(self, case: Union[str, Path], mapping: Any) -> Any:
        ...
