"""InspectIfc use case: inspects IFC models and returns inventory and spatial structure."""

from typing import Any, Dict, List, Optional
from ifc_to_fds.domain.bim import CanonicalModel


class InspectIfcUseCase:
    """Inspects IFC input files and extracts inventory, storeys, and MEP summary."""

    def __init__(self, model_preparer):
        self.model_preparer = model_preparer

    def execute(
        self,
        paths: List[str],
        configuration: Optional[Dict[str, Any]] = None,
    ) -> CanonicalModel:
        return self.model_preparer.prepare(paths, configuration or {}, reference=False)
