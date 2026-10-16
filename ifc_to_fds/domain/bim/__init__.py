"""Canonical BIM domain module."""

from .bounding_box import BoundingBox
from .model import (
    SCHEMA_VERSION,
    CanonicalElement,
    CanonicalModel,
    GeometryStatus,
    MappingStatus,
    MappingStrategy,
    OpeningReference,
    StoreyReference,
    TriangleMesh,
)

__all__ = [
    "SCHEMA_VERSION",
    "GeometryStatus",
    "MappingStatus",
    "MappingStrategy",
    "BoundingBox",
    "TriangleMesh",
    "OpeningReference",
    "StoreyReference",
    "CanonicalElement",
    "CanonicalModel",
]
