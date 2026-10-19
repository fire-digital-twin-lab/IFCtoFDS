"""Canonical BIM Model Schema (Compatibility Facade).

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
    "get_execution_provenance",
]


def get_execution_provenance():
    """Captures runtime environment versions for scientific audit reproducibility."""
    import platform
    import sys

    provenance = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
    }
    try:
        import ifcopenshell
        provenance["ifcopenshell_version"] = getattr(ifcopenshell, "__version__", "unknown")
    except ImportError:
        pass
    try:
        import trimesh
        provenance["trimesh_version"] = getattr(trimesh, "__version__", "unknown")
    except ImportError:
        pass
    return provenance

