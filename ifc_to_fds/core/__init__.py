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
)
from .inventory import extract_inventory
from .units import get_length_unit_scale

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
]
