"""Abstract output port for FDS serialization."""

from typing import Any, Protocol, Tuple, runtime_checkable


@runtime_checkable
class FdsExporterPort(Protocol):
    """Port for serializing canonical models into Fortran FDS namelists."""

    def serialize_fds(
        self,
        model: Any,
        all_geom: bool = False,
        include_review: bool = False,
        decisions: Any = None,
        boundary_policy: Any = None,
        mapping_plan: Any = None,
    ) -> Tuple[str, Any]:
        ...
