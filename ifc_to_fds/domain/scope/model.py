"""Scope domain models separating SelectionScope, SimulationDomain, and BoundaryPolicy."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from ..bim.bounding_box import BoundingBox


class ScopeDecision(str, Enum):
    IN_SCOPE = "IN_SCOPE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    BOUNDARY_RETAINED = "BOUNDARY_RETAINED"
    UNRESOLVED = "UNRESOLVED"


class BoundaryPolicy(str, Enum):
    PRESERVE_AND_BLOCK = "PRESERVE_AND_BLOCK"
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED_BOUNDARY_OBST_SINGLE_MESH = "VALIDATED_BOUNDARY_OBST_SINGLE_MESH"


class SelectionScope(BaseModel):
    """User-requested spatial selection scope."""

    model_config = ConfigDict(extra="forbid")
    name: str = "FullModel"
    bounding_box: Optional[BoundingBox] = None
    storeys: List[str] = Field(default_factory=list)
    include_connecting_structures: bool = True
    elements: List[str] = Field(default_factory=list)


# Backward compatibility alias
SpatialScope = SelectionScope
