"""Mapping intent and scope; emitted primitive identities remain serialization outputs."""

from ifc_to_fds.domain.mapping import MappingDecision, MappingPlan, MappingStrategy
from ifc_to_fds.domain.scope import SpatialScope, ScopeDecision

__all__ = ["MappingDecision", "MappingPlan", "MappingStrategy", "SpatialScope", "ScopeDecision"]
