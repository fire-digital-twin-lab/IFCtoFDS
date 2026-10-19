"""Application service for preparing canonical models with spatial scope and mapping plan."""

from time import perf_counter
from typing import Any, Dict, List
from ifc_to_fds.core.federation import load_sources
from ifc_to_fds.domain.bim import BoundingBox, CanonicalModel
from ifc_to_fds.domain.scope import SpatialScope
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.mapping.scope import apply_spatial_scope
from ifc_to_fds.application.dto.configuration import validate_configuration


def prepare_model(
    paths: List[str], configuration: Dict[str, Any], reference: bool = False
) -> CanonicalModel:
    """Prepares canonical model with spatial scoping, simulation domain, and mapping plan."""
    configuration = validate_configuration(configuration)
    source_opts = dict(configuration.get("sources") or {})
    for k in ("rebase_vector", "rebase_origin", "auto_rebase_origin"):
        if k in configuration:
            source_opts[k] = configuration[k]
    model = load_sources(paths, source_opts, reference=reference)
    scope_start = perf_counter()
    scope = SpatialScope.model_validate(configuration.get("scope", {}))
    if scope.storeys or scope.bounding_box:
        apply_spatial_scope(model, scope)
    else:
        model.requested_scope = scope.model_dump(mode="json")
    if configuration.get("simulation_domain"):
        model.simulation_domain = BoundingBox.model_validate(
            configuration["simulation_domain"]
        )
        model.domain_origin = "EXPLICIT_CONFIGURATION"
    elif not scope.storeys and not scope.bounding_box:
        model.simulation_domain = model.model_bounds
        model.domain_origin = "FULL_MODEL"
    mapping_start = perf_counter()
    plan_mapping(
        model,
        configuration.get("all_geom", False),
        configuration.get("include_review", False),
        configuration.get("decisions", {}),
        configuration.get("boundary_policy"),
        geometry_fidelity=configuration.get("profile") == "geometry-fidelity",
        system_decisions=configuration.get("system_decisions", {}),
    )
    model.timings.update(
        scope_s=mapping_start - scope_start, mapping_s=perf_counter() - mapping_start
    )
    included = {
        e.entity_key
        for e in model.elements
        if e.scope_decision.value in ("IN_SCOPE", "BOUNDARY_RETAINED")
    }
    for edge in model.mep_graph.connections:
        edge.boundary_connection = (edge.source_element_id in included) != (
            edge.target_element_id in included
        )
    return model
