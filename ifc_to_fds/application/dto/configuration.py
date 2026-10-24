"""Application configuration DTO and validation."""

import copy
import math
from typing import Any, Dict

from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.domain.scope import SpatialScope
from ifc_to_fds.domain.validation import AuditConfig
from ifc_to_fds.mapping.policy import validate_decisions


def validate_configuration(value: Any) -> Dict[str, Any]:
    """Validates and normalizes conversion and audit configuration."""
    if not isinstance(value, dict):
        raise ValueError("Configuration must be an object")
    config = copy.deepcopy(value)
    unknown = set(config) - {
        "sources",
        "scope",
        "audit",
        "all_geom",
        "include_review",
        "cell_size",
        "mep_graph",
        "simulation_domain",
        "profile",
        "reference_case",
        "decisions",
        "system_decisions",
        "intentional_deltas",
        "geometry_package_sha256",
        "boundary_policy",
        "rebase_vector",
        "rebase_origin",
        "auto_rebase_origin",
    }
    if unknown:
        raise ValueError(f"Unknown configuration fields: {sorted(unknown)}")
    if config.get("include_review"):
        raise ValueError(
            "include_review=True is not supported without explicit reviewed decisions; "
            "provide decisions with action='PASSIVE_OBSTACLE' and required promotion factors"
        )
    if config.get("profile", "mapping") not in (
        "mapping",
        "research-basement",
        "simulation",
        "geometry-fidelity",
    ):
        raise ValueError("Unknown acceptance profile")
    if config.get("reference_case") is not None and not isinstance(
        config["reference_case"], str
    ):
        raise ValueError("reference_case must be a case directory or registered ID")
    if config.get("simulation_domain") is not None:
        BoundingBox.model_validate(config["simulation_domain"])
    from ifc_to_fds.mapping.boundary import POLICY, EXACT_POLICY

    if config.get("boundary_policy") not in (None, POLICY, EXACT_POLICY):
        raise ValueError("Unsupported boundary policy")
    if (
        config.get("profile") == "geometry-fidelity"
        and config.get("simulation_domain")
        and not config.get("boundary_policy")
    ):
        config["boundary_policy"] = EXACT_POLICY
    validate_decisions(config.get("decisions", {}))
    validate_decisions(config.get("system_decisions", {}))
    SpatialScope.model_validate(config.get("scope", {}))
    AuditConfig.model_validate(config.get("audit", {}))
    if config.get("profile") == "geometry-fidelity":
        config.setdefault("audit", {}).setdefault("fail_fast_on_source_errors", True)
    sources = config.get("sources", {})
    if not isinstance(sources, dict) or set(sources) - {
        "common_coordinates",
        "transforms",
    }:
        raise ValueError("Invalid source coordinate configuration")
    for key in ("all_geom", "include_review"):
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{key} must be boolean")
    if "common_coordinates" in sources and not isinstance(
        sources["common_coordinates"], bool
    ):
        raise ValueError("common_coordinates must be boolean")
    if "transforms" in sources and not isinstance(sources["transforms"], dict):
        raise ValueError("transforms must be an object")
    cell = float(config.get("cell_size", 0.2))
    if not math.isfinite(cell) or cell <= 0:
        raise ValueError("cell_size must be finite and positive")
    config["cell_size"] = cell
    rebase_vector = config.get("rebase_vector")
    if rebase_vector is not None:
        if (
            not isinstance(rebase_vector, (list, tuple))
            or len(rebase_vector) != 3
            or any(
                isinstance(x, bool)
                or not isinstance(x, (int, float))
                or not math.isfinite(x)
                for x in rebase_vector
            )
        ):
            raise ValueError("rebase_vector must be [x,y,z] finite numbers")
    return config
