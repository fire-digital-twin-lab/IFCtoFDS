"""Abstract output port for IFC source ingestion and inventory extraction."""

from pathlib import Path
from typing import Any, Dict, List, Protocol, Union, runtime_checkable
from ifc_to_fds.domain.bim import CanonicalModel


@runtime_checkable
class IfcReaderPort(Protocol):
    """Port for parsing IFC files into canonical domain structures."""

    def load_sources(
        self,
        paths: List[str],
        configured_sources: Any = None,
        reference: bool = False,
    ) -> CanonicalModel:
        ...


@runtime_checkable
class InventoryReaderPort(Protocol):
    """Inventory-only query; callers do not receive an open native IFC handle."""

    def extract_inventory(self, path: Union[str, Path]) -> Dict[str, Any]:
        ...
