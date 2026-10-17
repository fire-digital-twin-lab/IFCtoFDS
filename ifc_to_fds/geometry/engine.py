"""Authoritative Geometry Engine powered by IfcOpenShell OpenCASCADE kernel.

Extracts meshes and reports kernel/topology failures explicitly. Extraction
does not establish independent geometry or opening verification.
"""

from typing import Any, List, Optional
import ifcopenshell
import ifcopenshell.geom
from ifc_to_fds.diagnostics import operation

from ifc_to_fds.core.canonical import (
    CanonicalElement,
    CanonicalModel,
    MappingStatus,
    TriangleMesh,
    GeometryStatus,
)
from .mesh import bounds_for_vertices, inspect_mesh_quality, as_trimesh, valid_solid


def create_geom_settings() -> Any:
    settings: Any = ifcopenshell.geom.settings()
    # Apply standard settings for world coordinate triangulated meshes
    settings.set(settings.USE_WORLD_COORDS, True)
    settings.set(settings.APPLY_DEFAULT_MATERIALS, False)
    settings.set(settings.WELD_VERTICES, True)
    settings.set("convert-back-units", False)
    settings.set("mesher-linear-deflection", 0.0001)
    return settings


def extract_element_geometry(
    ifc_file: ifcopenshell.file,
    element: CanonicalElement,
    settings: Any,
) -> Optional[TriangleMesh]:
    try:
        product = ifc_file.by_id(element.step_id)
    except Exception:
        return None

    if not getattr(product, "Representation", None):
        return None

    try:
        shape: Any = ifcopenshell.geom.create_shape(settings, product)
        geom = getattr(shape, "geometry", None)
        if geom is None:
            return None
        raw_verts = getattr(geom, "verts", [])
        raw_faces = getattr(geom, "faces", [])

        # Convert flat lists into triplets
        vertices: List[List[float]] = [
            [float(raw_verts[i]), float(raw_verts[i + 1]), float(raw_verts[i + 2])]
            for i in range(0, len(raw_verts), 3)
        ]
        faces: List[List[int]] = [
            [int(raw_faces[i]), int(raw_faces[i + 1]), int(raw_faces[i + 2])]
            for i in range(0, len(raw_faces), 3)
        ]

        mesh = TriangleMesh(vertices=vertices, faces=faces)
        quality = inspect_mesh_quality(mesh)
        mesh.is_closed_manifold = bool(quality["is_closed_manifold"])
        mesh.has_consistent_normals = quality["inconsistent_edges"] == 0

        return mesh
    except Exception as exc:
        element.mapping_status = MappingStatus.DEVIATED
        element.validation_notes.append(f"Geometry creation failed: {str(exc)}")
        return None


@operation("IFC_GEOMETRY")
def process_model_geometry(
    canonical_model: CanonicalModel,
    ifc_file: ifcopenshell.file,
) -> CanonicalModel:
    """Iterates through all elements in CanonicalModel and builds 3D meshes."""
    settings = create_geom_settings()

    all_verts: List[List[float]] = []

    # Iterator supports shared geometry and multiple CPU cores. Missing items are
    # retried individually so a failed iterator item remains visible in diagnostics.
    import os

    shapes = {}
    try:
        iterator = ifcopenshell.geom.iterator(
            settings, ifc_file, min(4, os.cpu_count() or 1)
        )
        if iterator.initialize():
            while True:
                shape = iterator.get()
                g = shape.geometry
                shapes[shape.id] = TriangleMesh(
                    vertices=[
                        list(g.verts[i : i + 3]) for i in range(0, len(g.verts), 3)
                    ],
                    faces=[list(g.faces[i : i + 3]) for i in range(0, len(g.faces), 3)],
                )
                if not iterator.next():
                    break
    except Exception as exc:
        for item in canonical_model.elements:
            item.validation_notes.append(f"Iterator fallback: {exc}")

    for elem in canonical_model.elements:
        if not elem.has_3d_geometry:
            elem.geometry_status = GeometryStatus.NO_REPRESENTATION
            continue

        mesh = shapes.get(elem.step_id) or extract_element_geometry(
            ifc_file, elem, settings
        )
        if mesh and mesh.vertices:
            elem.mesh = mesh
            bbox = bounds_for_vertices(mesh.vertices)
            elem.bounding_box = bbox
            if bbox:
                all_verts.append([bbox.xmin, bbox.ymin, bbox.zmin])
                all_verts.append([bbox.xmax, bbox.ymax, bbox.zmax])

            quality = inspect_mesh_quality(mesh)
            mesh.is_closed_manifold = bool(quality["is_closed_manifold"])
            mesh.has_consistent_normals = quality["inconsistent_edges"] == 0
            if valid_solid(mesh):
                tm = as_trimesh(mesh)
                mesh.volume, mesh.area = float(tm.volume), float(tm.area)
                elem.geometry_status = GeometryStatus.VALID
            else:
                elem.geometry_status = GeometryStatus.FAILED
                elem.validation_notes.append(f"Invalid solid: {quality}")
            for opening in elem.openings:
                opening_elem = CanonicalElement(
                    global_id=opening.opening_global_id,
                    step_id=opening.opening_step_id,
                    ifc_type="IfcOpeningElement",
                )
                opening.mesh = extract_element_geometry(
                    ifc_file, opening_elem, settings
                )
                if opening.mesh:
                    opening.bounding_box = bounds_for_vertices(opening.mesh.vertices)
                opening.extraction_diagnostic = opening_diagnostic(
                    opening.mesh, opening_elem.validation_notes
                )
        else:
            elem.geometry_status = GeometryStatus.FAILED
            if elem.has_3d_geometry and elem.mapping_status != MappingStatus.DEVIATED:
                elem.mapping_status = MappingStatus.UNSUPPORTED
                elem.validation_notes.append("No mesh generated by OpenCASCADE kernel.")

    if all_verts:
        canonical_model.model_bounds = bounds_for_vertices(all_verts)

    return canonical_model


def opening_diagnostic(mesh, notes):
    if mesh is None:
        return "; ".join(notes) or "No opening mesh generated"
    if not valid_solid(mesh):
        return f"Invalid opening solid: {inspect_mesh_quality(mesh)}"
    return None
