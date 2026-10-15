"""FDS Mapping Policy Engine.

Assigns appropriate FDS representation strategies (OBST, OBST+HOLE, GEOM,
SEMANTIC_ONLY, EXCLUDED_APPROVED) based on geometry topology and semantics.
"""

from typing import Set
from ifc_to_fds.core.canonical import CanonicalElement, MappingStrategy


SOLID_STRUCTURE_TYPES: Set[str] = {
    "IFCWALL",
    "IFCWALLSTANDARDCASE",
    "IFCSLAB",
    "IFCCOLUMN",
    "IFCBEAM",
    "IFCFOOTING",
    "IFCCOVERING",
}

COMPLEX_GEOM_TYPES: Set[str] = {
    "IFCROOF",
    "IFCSTAIR",
    "IFCSTAIRFLIGHT",
    "IFCRAMP",
    "IFCRAMPFLIGHT",
}

NON_OBSTACLE_TYPES: Set[str] = {
    "IFCSPACE",
    "IFCANNOTATION",
    "IFCSITE",
    "IFCVIRTUALELEMENT",
}


def determine_element_strategy(
    element: CanonicalElement,
    force_all_geom: bool = False,
    include_review_solids: bool = False,
) -> MappingStrategy:
    """Determines the target FDS mapping strategy for an element."""
    ifc_type = element.ifc_type.upper()

    if ifc_type in NON_OBSTACLE_TYPES or not element.has_3d_geometry or not element.mesh:
        return MappingStrategy.SEMANTIC_ONLY

    if force_all_geom:
        return MappingStrategy.GEOM

    if ifc_type in COMPLEX_GEOM_TYPES:
        return MappingStrategy.GEOM

    # Review solids (furnishing, MEP proxy)
    if ifc_type in {"IFCFURNISHINGELEMENT", "IFCBUILDINGELEMENTPROXY", "IFCRAILING"}:
        if include_review_solids:
            return MappingStrategy.OBST
        return MappingStrategy.EXCLUDED_APPROVED

    # Flow components
    if "FLOW" in ifc_type or "DUCT" in ifc_type or "PIPE" in ifc_type:
        if include_review_solids:
            return MappingStrategy.GEOM
        return MappingStrategy.SEMANTIC_ONLY

    if ifc_type in SOLID_STRUCTURE_TYPES:
        if element.openings:
            # Walls or slabs with openings: use GEOM or OBST_HOLE
            return MappingStrategy.GEOM
        return MappingStrategy.OBST

    return MappingStrategy.GEOM
