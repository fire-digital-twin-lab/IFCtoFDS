"""Core canonical BIM structures, units, and inventory."""

from .canonical import (
    BoundingBox,
    CanonicalElement,
    CanonicalModel,
    MappingStatus,
    MappingStrategy,
    MEPConnection,
    MEPGraph,
    MEPSystem,
    OpeningReference,
    PortReference,
    SourceMetadata,
    TriangleMesh,
    get_execution_provenance,
)

def __getattr__(name):
    # A native ingestion module imports core.canonical itself. Resolving these
    # compatibility exports eagerly would re-enter that partially loaded module.
    if name in {"extract_inventory", "get_length_unit_scale"}:
        from ifc_to_fds.modules.bim import api
        return getattr(api, name)
    raise AttributeError(name)

__all__ = [
    "BoundingBox",
    "CanonicalElement",
    "CanonicalModel",
    "MappingStatus",
    "MappingStrategy",
    "MEPConnection",
    "MEPGraph",
    "MEPSystem",
    "OpeningReference",
    "PortReference",
    "SourceMetadata",
    "TriangleMesh",
    "extract_inventory",
    "get_length_unit_scale",
    "get_execution_provenance",
]
