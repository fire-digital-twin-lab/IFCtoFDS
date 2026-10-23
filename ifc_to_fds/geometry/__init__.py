"""Geometry kernel and mesh inspection module."""

from ifc_to_fds.modules.geometry.infrastructure.ifcopenshell.extraction import (
    create_geom_settings,
    extract_element_geometry,
    process_model_geometry,
)
from ifc_to_fds.modules.geometry.algorithms.mesh import bounds_for_vertices, inspect_mesh_quality

__all__ = [
    "bounds_for_vertices",
    "create_geom_settings",
    "extract_element_geometry",
    "inspect_mesh_quality",
    "process_model_geometry",
]
