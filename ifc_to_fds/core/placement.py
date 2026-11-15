"""Placement provenance; matrices act on metre-valued column vectors."""

import math

import numpy as np
from ifcopenshell.util.placement import (
    get_local_placement,
    get_mappeditem_transformation,
)

RIGID_TOLERANCE = 1e-6


def is_rigid_rotation(rotation, tolerance=RIGID_TOLERANCE):
    """True for a proper rotation: RᵀR = I and det = +1 (no scale, shear or mirror)."""
    r = np.asarray(rotation, dtype=float)
    if r.shape != (3, 3) or not np.isfinite(r).all():
        return False
    return bool(
        abs(float(np.linalg.det(r)) - 1.0) <= tolerance
        and np.allclose(r.T @ r, np.eye(3), rtol=0.0, atol=tolerance)
    )


def _unit(vector, name):
    v = np.asarray(vector, dtype=float)
    length = float(np.linalg.norm(v))
    if not math.isfinite(length) or length < 1e-12:
        raise ValueError(f"IFC placement {name} has zero length")
    return v / length


def _axis_matrix(axis_placement):
    """IFC IfcAxis2Placement3D/2D to a 4x4 matrix with a rigid rotation.

    IFC (IfcBuildAxes) takes Z from Axis and derives X by projecting RefDirection
    onto the plane normal to Z. ifcopenshell's a2p does not project, so an oblique
    RefDirection gives a non-orthogonal matrix there.
    """
    if axis_placement is None:
        return np.eye(4)
    location = list(axis_placement.Location.Coordinates) + [0.0, 0.0]
    matrix = np.eye(4)
    matrix[:3, 3] = [float(c) for c in location[:3]]
    if axis_placement.is_a("IfcAxis2Placement3D"):
        z = _unit(axis_placement.Axis.DirectionRatios if axis_placement.Axis else (0, 0, 1), "Axis")
        ref = list(axis_placement.RefDirection.DirectionRatios) if axis_placement.RefDirection else [1, 0, 0]
    elif axis_placement.is_a("IfcAxis2Placement2D"):
        z = np.array([0.0, 0.0, 1.0])
        ref = list(axis_placement.RefDirection.DirectionRatios) if axis_placement.RefDirection else [1, 0]
        ref = ref + [0.0] * (3 - len(ref))
    else:
        raise ValueError(f"Unsupported IFC axis placement {axis_placement.is_a()}")
    ref = np.asarray(ref, dtype=float)
    x = ref - np.dot(ref, z) * z
    if float(np.linalg.norm(x)) < 1e-9 * max(1.0, float(np.linalg.norm(ref))):
        raise ValueError("IFC placement RefDirection is parallel to Axis")
    x = _unit(x, "RefDirection")
    matrix[:3, :3] = np.column_stack([x, np.cross(z, x), z])
    return matrix


def _ifc_chain_matrix(placement):
    matrix = np.eye(4)
    current = placement
    while current:
        matrix = _axis_matrix(current.RelativePlacement) @ matrix
        current = current.PlacementRelTo
    return matrix


def _local_placement_matrix(placement):
    """ifcopenshell's matrix when it is a rotation, else the IFC-conformant one."""
    matrix = np.asarray(get_local_placement(placement), dtype=float)
    if is_rigid_rotation(matrix[:3, :3]):
        return matrix
    return _ifc_chain_matrix(placement)


def extract_placement(product, scale):
    value = dict(
        status="UNVERIFIED",
        units="METRE",
        matrix_order="ROW_MAJOR",
        vector_convention="COLUMN",
        source_unit_scale=scale,
        chain=[],
        mapped_items=[],
    )
    placement = getattr(product, "ObjectPlacement", None)
    if placement is None:
        value.update(status="MISSING", reason="IFC product has no ObjectPlacement")
        return value
    try:
        seen = set()
        current = placement
        while current:
            if current.id() in seen or not current.is_a("IfcLocalPlacement"):
                raise ValueError("Cyclic or unsupported IFC placement")
            seen.add(current.id())
            value["chain"].append(current.id())
            current = current.PlacementRelTo
        matrix = _local_placement_matrix(placement)
        matrix[:3, 3] *= scale
        if not np.isfinite(matrix).all():
            raise ValueError("Nonfinite IFC placement")
        if not is_rigid_rotation(matrix[:3, :3]):
            raise ValueError("IFC placement is not a rigid transform")
        value.update(
            status="CONFIRMED",
            ifc_local_to_model=matrix.ravel().tolist(),
            model_to_common_world=np.eye(4).ravel().tolist(),
            effective_world=matrix.ravel().tolist(),
        )
        visited = set()

        def walk(items, parent=None):
            for item in items:
                if not item.is_a("IfcMappedItem"):
                    continue
                if item.id() in visited:
                    raise ValueError(
                        "Cyclic/repeated mapped representation requires review"
                    )
                visited.add(item.id())
                mapped = np.asarray(get_mappeditem_transformation(item), dtype=float)
                mapped[:3, 3] *= scale
                if not np.isfinite(mapped).all():
                    raise ValueError("Nonfinite mapped representation")
                value["mapped_items"].append(
                    dict(
                        step_id=item.id(),
                        parent_step_id=parent,
                        mapping_source_step_id=item.MappingSource.id(),
                        matrix=mapped.ravel().tolist(),
                    )
                )
                walk(item.MappingSource.MappedRepresentation.Items, item.id())
                visited.remove(item.id())

        for representation in getattr(
            getattr(product, "Representation", None), "Representations", []
        ):
            walk(representation.Items)
    except Exception as exc:
        value.update(status="UNVERIFIED", reason=str(exc))
    return value


def federate_placement(element, matrix):
    if element.placement.get("status") == "CONFIRMED":
        local = np.asarray(element.placement["ifc_local_to_model"]).reshape(4, 4)
        element.placement["model_to_common_world"] = matrix.ravel().tolist()
        element.transform = (matrix @ local).ravel().tolist()
        element.placement["effective_world"] = element.transform
