"""Stored geometry evidence consumed without depending on a disk adapter."""

from typing import Any, Protocol, runtime_checkable

from ifc_to_fds.domain.bim import BoundingBox, TriangleMesh


@runtime_checkable
class StoredGeometryEvidence(Protocol):
    @property
    def index(self) -> dict[str, Any]: ...

    def verify(self) -> None: ...

    def verify_index(self) -> None: ...
