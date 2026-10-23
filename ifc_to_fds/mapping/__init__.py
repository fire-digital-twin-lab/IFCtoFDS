"""FDS mapping, scoping, and serialization module."""

from ifc_to_fds.modules.fds.application.serializer import serialize_fds
from ifc_to_fds.modules.fds.application.manifest_builder import MappingManifest, build_manifest
from ifc_to_fds.modules.simulation.application.mapping_policy import determine_element_strategy
from ifc_to_fds.modules.simulation.application.spatial_scope import SpatialScope, apply_spatial_scope

__all__ = [
    "MappingManifest",
    "SpatialScope",
    "apply_spatial_scope",
    "build_manifest",
    "determine_element_strategy",
    "serialize_fds",
]
