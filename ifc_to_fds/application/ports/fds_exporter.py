"""Abstract output port for FDS serialization."""

from typing import Optional, Protocol, Tuple, runtime_checkable

from ifc_to_fds.domain.bim import CanonicalModel
from ifc_to_fds.domain.mapping import MappingManifest, MappingPlan


@runtime_checkable
class FdsExporterPort(Protocol):
    """Port for serializing canonical models into Fortran FDS namelists."""

    def serialize_fds(
        self,
        model: CanonicalModel,
        cell_size: Optional[float] = None,
        mapping_plan: Optional[MappingPlan] = None,
    ) -> Tuple[str, MappingManifest]:
        ...
