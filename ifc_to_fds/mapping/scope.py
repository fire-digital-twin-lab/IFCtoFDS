"""Spatial Scope Filtering Engine.

Enables precise geometric clipping by 3D bounding box or building storey,
ensuring connecting structural members (stairs, shafts, columns) crossing
boundaries are preserved with explicit rationale rather than silently omitted.
"""

from typing import List, Optional, Set
from pydantic import BaseModel, Field

from ifc_to_fds.core.canonical import (
    BoundingBox,
    CanonicalModel,
    MappingStatus,
    MappingStrategy,
)


class SpatialScope(BaseModel):
    name: str = "FullModel"
    bounding_box: Optional[BoundingBox] = None
    storeys: List[str] = Field(default_factory=list)
    include_connecting_structures: bool = True
    connecting_types: Set[str] = Field(
        default_factory=lambda: {
            "IFCSTAIR",
            "IFCSTAIRFLIGHT",
            "IFCRAMP",
            "IFCRAMPFLIGHT",
            "IFCCOLUMN",
            "IFCMEMBER",
        }
    )


def apply_spatial_scope(model: CanonicalModel, scope: SpatialScope) -> CanonicalModel:
    """Filters model elements according to spatial scope."""
    if not scope.bounding_box and not scope.storeys:
        return model

    for elem in model.elements:
        # Check Storey match
        storey_match = (not scope.storeys) or (elem.storey in scope.storeys)

        # Check Bounding Box match
        bbox_match = True
        if scope.bounding_box:
            if elem.bounding_box:
                bbox_match = scope.bounding_box.intersects(elem.bounding_box)
            else:
                bbox_match = False

        is_connecting = elem.ifc_type.upper() in scope.connecting_types

        if storey_match and bbox_match:
            # Fully inside scope
            continue
        elif scope.include_connecting_structures and is_connecting and (storey_match or bbox_match):
            # Preserved as a boundary-spanning element
            elem.mapping_rationale = "Preserved as vertical connecting structure intersecting spatial scope."
        else:
            # Excluded outside scope
            elem.mapping_strategy = MappingStrategy.EXCLUDED_APPROVED
            elem.mapping_status = MappingStatus.EXCLUDED_APPROVED
            elem.mapping_rationale = f"Outside selected spatial scope (Storey: {elem.storey})."

    return model
