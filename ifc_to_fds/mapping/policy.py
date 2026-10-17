"""Versioned decisions; no implicit approval of generic/review objects."""

from ifc_to_fds.core.canonical import MappingStrategy, MappingStatus, ScopeDecision
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
PROMOTION_FACTORS = {
    "ifc_type",
    "mesh_scale",
    "domain_position",
    "airflow_clearance",
    "system",
    "future_operational_role",
    "golden_policy",
}


def validate_decisions(decisions):
    if not isinstance(decisions, dict):
        raise ValueError("decisions must map entity keys to explicit decisions")
    for key, decision in decisions.items():
        if not isinstance(decision, dict) or set(decision) - {
            "action",
            "policy_version",
            "rationale",
            "reviewer",
            "evidence",
            "factors",
        }:
            raise ValueError(f"Invalid decision: {key}")
        if decision.get("action") not in (
            "EXCLUDE",
            "REFERENCE_GEOMETRY",
            "PASSIVE_OBSTACLE",
        ):
            raise ValueError(f"Invalid decision action: {key}")
        if not all(
            decision.get(k)
            for k in ("policy_version", "rationale", "reviewer", "evidence")
        ):
            raise ValueError(
                f"Decision requires policy version, rationale, reviewer and evidence: {key}"
            )
        if decision["action"] == "PASSIVE_OBSTACLE" and (
            not isinstance(decision.get("factors"), dict)
            or set(decision["factors"]) != PROMOTION_FACTORS
            or not all(
                isinstance(v, str) and v.strip() for v in decision["factors"].values()
            )
        ):
            raise ValueError(
                f"Promotion requires all simulation relevance factors: {key}"
            )


def determine_element_strategy(
    element, force_all_geom=False, include_review_solids=False
):
    if element.scope_decision == ScopeDecision.OUT_OF_SCOPE:
        return MappingStrategy.EXCLUDED_SCOPE
    if element.ifc_type.upper() in NON_OBSTACLE_TYPES or element.role != "PHYSICAL":
        return MappingStrategy.SEMANTIC_ONLY
    if element.review_status == "EXCLUDED_APPROVED":
        return MappingStrategy.EXCLUDED_APPROVED
    if element.simulation_role == "REFERENCE_GEOMETRY" or (
        element.boundary_treatment == "PENDING_VALIDATION"
        and element.representation_bounds is None
    ):
        return MappingStrategy.NONE
    if not element.mesh or not valid_solid(element.mesh) or any(
        not o.mesh or not valid_solid(o.mesh) for o in element.openings
    ):
        return MappingStrategy.NONE
    if (
        not force_all_geom
        and not element.openings
        and is_axis_aligned_box(element.mesh)
    ):
        return MappingStrategy.OBST
    return MappingStrategy.GEOM


def plan_mapping(
    model,
    force_all_geom=False,
    include_review_solids=False,
    decisions=None,
    boundary_policy=None,
):
    decisions = decisions or {}
    validate_decisions(decisions)
    unknown = set(decisions) - {e.entity_key for e in model.elements}
    if unknown:
        raise ValueError(f"Decisions refer to unknown entities: {sorted(unknown)}")
    for e in model.elements:
        e.fds_primitive_ids = []
        e.decision = decisions.get(e.entity_key, {})
        e.review_status = "NOT_REQUIRED"
        is_review = e.ifc_type.upper() in REVIEW_TYPES
        is_mep = bool(
            e.classification_evidence
            or e.system_ids
            or e.ports
            or (e.type_class or "")
            .upper()
            .startswith(("IFCDUCT", "IFCPIPE", "IFCFAN", "IFCVALVE"))
        )
        e.simulation_role = (
            "REFERENCE_GEOMETRY" if is_mep or is_review else "PASSIVE_OBSTACLE"
        )
        e.operational_status = (
            "NOT_CONFIGURED"
            if e.simulation_role == "REFERENCE_GEOMETRY"
            else "NOT_APPLICABLE"
        )
        if is_review:
            e.review_status = "REVIEW_REQUIRED"
        if e.decision:
            e.review_status = (
                "EXCLUDED_APPROVED" if e.decision["action"] == "EXCLUDE" else "APPROVED"
            )
            if e.decision["action"] != "EXCLUDE":
                e.simulation_role = e.decision["action"]
                e.operational_status = (
                    "NOT_CONFIGURED"
                    if e.simulation_role == "REFERENCE_GEOMETRY"
                    else "NOT_APPLICABLE"
                )
        e.boundary_treatment = "NOT_APPLICABLE"
        e.boundary_policy = None
        e.boundary_evidence = {}
        e.representation_bounds = None
        if (
            e.scope_decision
            in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
            and e.role == "PHYSICAL"
            and e.bounding_box
            and model.simulation_domain
        ):
            b, d = e.bounding_box.to_xb(), model.simulation_domain.to_xb()
            if any(
                b[i] < d[i] - 1e-8 if i % 2 == 0 else b[i] > d[i] + 1e-8
                for i in range(6)
            ):
                e.boundary_treatment = "PENDING_VALIDATION"
                from .boundary import POLICY, eligible_bounds

                if boundary_policy == POLICY:
                    bounds = eligible_bounds(e, model, force_all_geom)
                    if bounds:
                        e.boundary_policy = POLICY
                        e.representation_bounds = bounds
        e.mapping_strategy = determine_element_strategy(
            e, force_all_geom, include_review_solids
        )
        e.fds_representation = (
            e.mapping_strategy.value
            if e.mapping_strategy in (MappingStrategy.OBST, MappingStrategy.GEOM)
            else "NONE"
        )
        e.mapping_planned = True
        e.geometry_preservation = "NOT_RUN"
        e.mapping_status = MappingStatus.INCONCLUSIVE
        e.mapping_rationale = e.decision.get(
            "rationale", "Policy 0.4: independently audit geometry, role and scope"
        )
        if e.mapping_strategy == MappingStrategy.EXCLUDED_SCOPE:
            e.mapping_status = MappingStatus.EXCLUDED_SCOPE
            e.mapping_rationale = e.scope_rationale
        elif e.mapping_strategy == MappingStrategy.EXCLUDED_APPROVED:
            e.mapping_status = MappingStatus.EXCLUDED_APPROVED
        elif e.mapping_strategy == MappingStrategy.SEMANTIC_ONLY:
            e.mapping_status = MappingStatus.SEMANTIC_ONLY
        elif e.role == "PHYSICAL" and (not e.mesh or not valid_solid(e.mesh) or any(
            not o.mesh or not valid_solid(o.mesh) for o in e.openings
        )):
            e.mapping_status = MappingStatus.UNSUPPORTED
            e.geometry_preservation = "FAILED" if e.mesh and not valid_solid(e.mesh) else "INCONCLUSIVE"
            e.mapping_rationale = (
                "Source physical geometry is missing or invalid; no FDS representation authorized. "
                + "; ".join(e.validation_notes)
                + "; ".join(f"Opening STEP {o.opening_step_id}: {getattr(o, 'extraction_diagnostic', None) or 'missing or invalid opening solid'}"
                            for o in e.openings if not o.mesh or not valid_solid(o.mesh))
            )
        elif e.review_status == "REVIEW_REQUIRED":
            e.mapping_status = MappingStatus.REVIEW_REQUIRED
    return model
