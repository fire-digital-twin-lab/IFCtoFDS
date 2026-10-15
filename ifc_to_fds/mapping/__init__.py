"""FDS mapping, scoping, and serialization module."""

from .exporter import serialize_fds
from .manifest import MappingManifest, build_manifest
from .policy import determine_element_strategy
from .scope import SpatialScope, apply_spatial_scope

__all__ = [
    "MappingManifest",
    "SpatialScope",
    "apply_spatial_scope",
    "build_manifest",
    "determine_element_strategy",
    "serialize_fds",
]
