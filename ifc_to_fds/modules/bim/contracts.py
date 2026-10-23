"""BIM contracts: source identity and the canonical source model have one definition."""

from ifc_to_fds.domain.bim import BoundingBox, CanonicalElement, CanonicalModel, TriangleMesh
from ifc_to_fds.domain.source import SourceIdentity, SourceMetadata
from ifc_to_fds.domain.mep import MEPGraph, MEPSystem, PortReference

__all__ = ["SourceIdentity", "SourceMetadata", "CanonicalElement", "CanonicalModel", "BoundingBox", "TriangleMesh", "MEPGraph", "MEPSystem", "PortReference"]
