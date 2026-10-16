"""Explicit, scope-preserving mapping decisions made before serialization."""

from ifc_to_fds.core.canonical import (
    MappingStrategy,
    MappingStatus,
    ScopeDecision,
)
from ifc_to_fds.geometry.mesh import is_axis_aligned_box, valid_solid

NON_OBSTACLE_TYPES = {
    "IFCSPACE",
    "IFCANNOTATION",
    "IFCSITE",
    "IFCVIRTUALELEMENT",
    "IFCBUILDING",
    "IFCBUILDINGSTOREY",
    "IFCPROJECT",
    "IFCOPENINGELEMENT",
    "IFCDISTRIBUTIONPORT",
}
REVIEW_TYPES = {"IFCFURNISHINGELEMENT", "IFCBUILDINGELEMENTPROXY", "IFCRAILING"}


def determine_element_strategy(
    element, force_all_geom=False, include_review_solids=False
):
    if element.scope_decision == ScopeDecision.OUT_OF_SCOPE:
        return MappingStrategy.EXCLUDED_APPROVED
    if element.ifc_type.upper() in NON_OBSTACLE_TYPES or element.role != "PHYSICAL":
        return MappingStrategy.SEMANTIC_ONLY
    if element.ifc_type.upper() in REVIEW_TYPES and not include_review_solids:
        return MappingStrategy.EXCLUDED_APPROVED
    # Missing/failed geometry is still required, not silently semantic-only.
    if not element.mesh or not valid_solid(element.mesh):
        return MappingStrategy.GEOM
    if (
        not force_all_geom
        and not element.openings
        and is_axis_aligned_box(element.mesh)
    ):
        return MappingStrategy.OBST
    return MappingStrategy.GEOM


def plan_mapping(model, force_all_geom=False, include_review_solids=False):
    for e in model.elements:
        e.mapping_strategy = determine_element_strategy(
            e, force_all_geom, include_review_solids
        )
        e.mapping_planned = True
        e.fds_primitive_ids = []
        if e.mapping_strategy == MappingStrategy.EXCLUDED_APPROVED:
            e.mapping_status = MappingStatus.EXCLUDED_APPROVED
            e.mapping_rationale = (
                e.scope_rationale
                if e.scope_decision == ScopeDecision.OUT_OF_SCOPE
                else "Explicit review-solid exclusion policy"
            )
        elif e.mapping_strategy == MappingStrategy.SEMANTIC_ONLY:
            e.mapping_status = MappingStatus.SEMANTIC_ONLY
            e.mapping_rationale = "Spatial, annotation, opening or port entity; retained in inventory and relationships"
        else:
            e.mapping_status = MappingStatus.INCONCLUSIVE
            e.mapping_rationale = "Physical solid required; awaiting independent audit"
    return model
