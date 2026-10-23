"""Published canonical model contracts (one definition per model).

Re-exports domain models from ifc_to_fds.domain to preserve full backward
compatibility for existing callers and tests.
"""

from ifc_to_fds.domain.bim import (
    SCHEMA_VERSION,
    BoundingBox,
    CanonicalElement,
    CanonicalModel,
    GeometryStatus,
    MappingStatus,
    MappingStrategy,
    OpeningReference,
    StoreyReference,
    TriangleMesh,
)
from ifc_to_fds.domain.mep import MEPConnection, MEPGraph, MEPSystem, PortReference
from ifc_to_fds.domain.scope import ScopeDecision
from ifc_to_fds.domain.source import SourceMetadata

__all__ = [
    "SCHEMA_VERSION",
    "ScopeDecision",
    "GeometryStatus",
    "MappingStatus",
    "MappingStrategy",
    "SourceMetadata",
    "BoundingBox",
    "TriangleMesh",
    "OpeningReference",
    "PortReference",
    "CanonicalElement",
    "MEPSystem",
    "MEPConnection",
    "MEPGraph",
    "StoreyReference",
    "CanonicalModel",
]

