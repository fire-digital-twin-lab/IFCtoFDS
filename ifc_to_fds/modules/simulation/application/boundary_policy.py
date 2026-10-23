"""Boundary representations derived from immutable source meshes."""

import hashlib
import json
from pathlib import Path
from ifc_to_fds.domain.contracts import BoundingBox
from ifc_to_fds.modules.geometry.api import valid_solid, is_axis_aligned_box, box_mesh

POLICY = "VALIDATED_BOUNDARY_OBST_SINGLE_MESH"
EXACT_POLICY = "SOURCE_SOLID_DOMAIN_INTERSECTION"
VERSION = "1.0.0"
FIXTURES = {
    "inside",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
    "zmin",
    "zmax",
    "corner",
    "offgrid",
    "thin",
    "passage",
    "closed_passage",
    "rejected",
}


from ifc_to_fds.modules.simulation.infrastructure.implementation_digest import adapter_digest


def eligible_bounds(element, model, force_all_geom=False):
    if (
        force_all_geom
        or model.domain_origin != "EXPLICIT_CONFIGURATION"
        or not model.simulation_domain
        or element.simulation_role != "PASSIVE_OBSTACLE"
        or element.review_status not in ("NOT_REQUIRED", "APPROVED")
        or element.ifc_type.upper()
        not in ("IFCCOLUMN", "IFCWALL", "IFCWALLSTANDARDCASE", "IFCBEAM", "IFCSLAB")
        or element.classification_evidence
        or element.system_ids
        or element.ports
        or element.openings
        or (element.type_class or "")
        .upper()
        .startswith(("IFCDUCT", "IFCPIPE", "IFCFAN", "IFCVALVE"))
        or not element.mesh
        or not valid_solid(element.mesh)
        or not is_axis_aligned_box(element.mesh)
    ):
        return None
    a, b = element.bounding_box.to_xb(), model.simulation_domain.to_xb()
    values = [max(a[i], b[i]) if i % 2 == 0 else min(a[i], b[i]) for i in range(6)]
    if any(values[i + 1] <= values[i] for i in (0, 2, 4)):
        return None
    return BoundingBox(
        **dict(zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), values))
    )


def target_mesh(element):
    if element.boundary_policy == EXACT_POLICY and element.representation_bounds:
        return intersect_solid(element.mesh, element.representation_bounds)
    return (
        box_mesh(element.representation_bounds)
        if element.boundary_policy == POLICY and element.representation_bounds
        else element.mesh
    )


def intersect_solid(mesh, bounds):
    """Intersect actual triangulated solid, including voids, with a domain box."""
    from ifc_to_fds.modules.geometry.api import solid_boolean
    from ifc_to_fds.modules.geometry.api import as_trimesh
    from ifc_to_fds.domain.contracts import TriangleMesh

    solid = solid_boolean(
        [as_trimesh(mesh), as_trimesh(box_mesh(bounds))], "intersection"
    )
    if not solid.is_volume or solid.volume <= 0:
        raise ValueError(
            "Domain intersection has no valid positive-volume source solid"
        )
    return TriangleMesh(vertices=solid.vertices.tolist(), faces=solid.faces.tolist())


def exact_bounds(element, model):
    from ifc_to_fds.modules.geometry.api import bounds_for_vertices

    if (
        model.domain_origin != "EXPLICIT_CONFIGURATION"
        or not model.simulation_domain
        or element.simulation_role != "PASSIVE_OBSTACLE"
        or element.review_status not in ("NOT_REQUIRED", "APPROVED")
        or not element.mesh
        or not valid_solid(element.mesh)
    ):
        return None
    # Bounds are measured from the intersected solid, never used as a proxy solid.
    clipped = intersect_solid(element.mesh, model.simulation_domain)
    return bounds_for_vertices(clipped.vertices)


