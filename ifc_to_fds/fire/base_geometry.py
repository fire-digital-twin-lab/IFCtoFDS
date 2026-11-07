"""Verified emitted base geometry used by scientific scenario gates."""

from __future__ import annotations

from dataclasses import dataclass

from ifc_to_fds.domain.bim import TriangleMesh


@dataclass(frozen=True)
class VerifiedBaseGeometry:
    """Exact emitted GEOM evidence reconstructed from a sealed FDS artifact."""

    geom_meshes: dict[str, tuple[TriangleMesh, ...]]
    geom_primitive_ids: dict[str, tuple[str, ...]]

    def meshes_for(self, entity_key: str) -> tuple[TriangleMesh, ...]:
        return self.geom_meshes.get(entity_key, ())


__all__ = ["VerifiedBaseGeometry"]
