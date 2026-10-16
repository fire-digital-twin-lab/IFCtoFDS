"""Placement provenance; matrices act on metre-valued column vectors."""

import numpy as np
from ifcopenshell.util.placement import (
    get_local_placement,
    get_mappeditem_transformation,
)


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
        matrix = np.asarray(get_local_placement(placement), dtype=float)
        matrix[:3, 3] *= scale
        if not np.isfinite(matrix).all():
            raise ValueError("Nonfinite IFC placement")
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
