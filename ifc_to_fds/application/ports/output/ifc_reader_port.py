"""Abstract output port for IFC source ingestion and inventory extraction."""

from pathlib import Path
from typing import Any, Dict, List, Protocol, Union, runtime_checkable


@runtime_checkable
class IfcReaderPort(Protocol):
    """Port for parsing IFC files into canonical domain structures."""

    def load_sources(
        self,
        paths: List[str],
        configured_sources: Any = None,
        reference: bool = False,
    ) -> Any:
        ...

    def extract_inventory(self, path: Union[str, Path]) -> Dict[str, Any]:
        ...
