"""Canonical BIM Model Schema.

Defines the strongly-typed intermediate data structures mediating between
raw IFC STEP entities, the geometric kernel, the MEP topological graph,
and the FDS serialized output.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator
import math

SCHEMA_VERSION = "0.4.0"


class ScopeDecision(str, Enum):
    IN_SCOPE = "IN_SCOPE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    BOUNDARY_RETAINED = "BOUNDARY_RETAINED"
    UNRESOLVED = "UNRESOLVED"


class GeometryStatus(str, Enum):
    NOT_PROCESSED = "NOT_PROCESSED"
    VALID = "VALID"
    FAILED = "FAILED"
    NO_REPRESENTATION = "NO_REPRESENTATION"


class MappingStatus(str, Enum):
    EXCLUDED_SCOPE = "EXCLUDED_SCOPE"
    REFERENCE_PRESERVED = "REFERENCE_PRESERVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    MATCHED = "MATCHED"
    DEVIATED = "DEVIATED"
    MISSING = "MISSING"
    SEMANTIC_ONLY = "SEMANTIC_ONLY"
    EXCLUDED_APPROVED = "EXCLUDED_APPROVED"
    UNSUPPORTED = "UNSUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    MISSING_SOURCE_DATA = "MISSING_SOURCE_DATA"


class MappingStrategy(str, Enum):
    NONE = "NONE"
    EXCLUDED_SCOPE = "EXCLUDED_SCOPE"
    OBST = "OBST"
    OBST_HOLE = "OBST_HOLE"
    GEOM = "GEOM"
    VOXEL = "VOXEL"
    SEMANTIC_ONLY = "SEMANTIC_ONLY"
    EXCLUDED_APPROVED = "EXCLUDED_APPROVED"


class SourceMetadata(BaseModel):
    source_id: str = ""
    filename: str
    file_path: str
    file_hash_sha256: str
    file_size_bytes: int
    schema_version: str  # e.g., "IFC4", "IFC2X3"
    unit_length_name: str = "METRE"
    unit_scale_to_meters: float = 1.0
    world_transform: List[float] = Field(
        default_factory=lambda: [
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ]
    )


class BoundingBox(BaseModel):
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float

    @model_validator(mode="after")
    def valid_bounds(self):
        if not all(math.isfinite(v) for v in self.to_xb()):
            raise ValueError("Bounds must be finite")
        if self.xmax <= self.xmin or self.ymax <= self.ymin or self.zmax <= self.zmin:
            raise ValueError("Bounds must have positive extents")
        return self

    @property
    def dx(self) -> float:
        return max(0.0, self.xmax - self.xmin)

    @property
    def dy(self) -> float:
        return max(0.0, self.ymax - self.ymin)

    @property
    def dz(self) -> float:
        return max(0.0, self.zmax - self.zmin)

    @property
    def volume(self) -> float:
        return self.dx * self.dy * self.dz

    def to_xb(self) -> List[float]:
        return [self.xmin, self.xmax, self.ymin, self.ymax, self.zmin, self.zmax]

    def contains_point(self, x: float, y: float, z: float, tol: float = 1e-4) -> bool:
        return (
            (self.xmin - tol <= x <= self.xmax + tol)
            and (self.ymin - tol <= y <= self.ymax + tol)
            and (self.zmin - tol <= z <= self.zmax + tol)
        )

    def intersects(self, other: BoundingBox, tol: float = 1e-4) -> bool:
        return not (
            self.xmax < other.xmin - tol
            or self.xmin > other.xmax + tol
            or self.ymax < other.ymin - tol
            or self.ymin > other.ymax + tol
            or self.zmax < other.zmin - tol
            or self.zmin > other.zmax + tol
        )


class TriangleMesh(BaseModel):
    # vertices: list of [x, y, z] floats
    vertices: List[List[float]] = Field(default_factory=list)
    # faces: list of [v0, v1, v2] zero-indexed triangle indices
    faces: List[List[int]] = Field(default_factory=list)
    normals: Optional[List[List[float]]] = None
    is_closed_manifold: Optional[bool] = None
    has_consistent_normals: Optional[bool] = None
    area: Optional[float] = None
    volume: Optional[float] = None


class OpeningReference(BaseModel):
    opening_global_id: str
    opening_step_id: int
    opening_name: str
    opening_type: str = "IfcOpeningElement"
    bounding_box: Optional[BoundingBox] = None
    filling_global_ids: List[str] = Field(default_factory=list)
    is_subtracted: bool = False
    mesh: Optional[TriangleMesh] = None
    verification_status: str = "NOT_RUN"


class PortReference(BaseModel):
    port_global_id: str
    port_step_id: int
    name: Optional[str] = None
    flow_direction: Optional[str] = None  # SINK, SOURCE, SOURCEANDSINK, NOTDEFINED
    local_position: Optional[List[float]] = None
    connected_port_ids: List[str] = Field(default_factory=list)
    port_key: str = ""
    world_position: Optional[List[float]] = None
    owner_key: str = ""


class CanonicalElement(BaseModel):
    building_id: Optional[str] = None
    spatial_ancestry: List[str] = Field(default_factory=list)
    type_class: Optional[str] = None
    source_presence: str = "CONFIRMED"
    geometry_preservation: str = "NOT_RUN"
    simulation_role: str = "PASSIVE_OBSTACLE"
    operational_status: str = "NOT_APPLICABLE"
    fds_representation: str = "NONE"
    review_status: str = "NOT_REQUIRED"
    boundary_treatment: str = "NOT_APPLICABLE"
    decision: Dict[str, Any] = Field(default_factory=dict)
    source_id: str = ""
    entity_key: str = ""
    global_id: str
    step_id: int
    ifc_type: str
    name: str = ""
    tag: Optional[str] = None
    storey: Optional[str] = None
    storey_id: Optional[str] = None
    role: str = "PHYSICAL"
    geometry_status: GeometryStatus = GeometryStatus.NOT_PROCESSED
    scope_decision: ScopeDecision = ScopeDecision.IN_SCOPE
    scope_rationale: str = "Full model"
    mapping_planned: bool = False
    mep_category: str = "OTHER"
    classification_evidence: List[str] = Field(default_factory=list)
    predefined_type: Optional[str] = None
    system_names: List[str] = Field(default_factory=list)
    system_ids: List[str] = Field(default_factory=list)

    # Transform: 4x4 matrix row-major in world coordinates
    transform: Optional[List[float]] = None

    # Geometric representation
    bounding_box: Optional[BoundingBox] = None
    mesh: Optional[TriangleMesh] = None
    has_3d_geometry: bool = False

    # Relationships
    host_global_id: Optional[str] = None
    openings: List[OpeningReference] = Field(default_factory=list)
    ports: List[PortReference] = Field(default_factory=list)
    property_sets: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Mapping Decisions & Provenance
    mapping_strategy: MappingStrategy = MappingStrategy.SEMANTIC_ONLY
    mapping_status: MappingStatus = MappingStatus.INCONCLUSIVE
    mapping_rationale: Optional[str] = None
    fds_primitive_ids: List[str] = Field(default_factory=list)
    validation_notes: List[str] = Field(default_factory=list)


class MEPSystem(BaseModel):
    system_id: str
    name: str
    system_type: (
        str  # e.g., "VENTILATION", "SMOKE_EXTRACT", "FIRE_SUPPRESSION", "PLUMBING"
    )
    element_global_ids: List[str] = Field(default_factory=list)
    is_fire_safety_critical: bool = False
    element_keys: List[str] = Field(default_factory=list)


class MEPConnection(BaseModel):
    connection_id: str
    source_element_id: str
    source_port_id: str
    target_element_id: str
    target_port_id: str
    relation_type: str  # "EXPLICIT_IFC", "GEOMETRIC_PROXIMITY"
    distance_meters: float = 0.0
    boundary_connection: bool = False


class MEPGraph(BaseModel):
    systems: List[MEPSystem] = Field(default_factory=list)
    connections: List[MEPConnection] = Field(default_factory=list)
    isolated_element_ids: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    coverage: Dict[str, Any] = Field(default_factory=dict)


class StoreyReference(BaseModel):
    building_id: Optional[str] = None
    spatial_ancestry: List[str] = Field(default_factory=list)
    storey_id: str
    source_id: str
    name: str
    elevation_m: Optional[float] = None


class CanonicalModel(BaseModel):
    simulation_domain: Optional[BoundingBox] = None
    domain_origin: str = "UNRESOLVED"
    schema_version: str = SCHEMA_VERSION
    source: SourceMetadata
    sources: List[SourceMetadata] = Field(default_factory=list)
    elements: List[CanonicalElement] = Field(default_factory=list)
    mep_graph: MEPGraph = Field(default_factory=MEPGraph)
    storeys: List[str] = Field(default_factory=list)
    model_bounds: Optional[BoundingBox] = None
    storey_references: List[StoreyReference] = Field(default_factory=list)
    requested_scope: Dict[str, Any] = Field(default_factory=dict)
    exported_bounds: Optional[BoundingBox] = None
    timings: Dict[str, float] = Field(default_factory=dict)

    def get_element_by_guid(self, guid: str) -> Optional[CanonicalElement]:
        matches = [el for el in self.elements if el.global_id == guid]
        if len(matches) > 1:
            raise ValueError("Ambiguous GlobalId; use entity_key")
        return matches[0] if matches else None

    def get_elements_by_type(self, ifc_type: str) -> List[CanonicalElement]:
        t_upper = ifc_type.upper()
        return [el for el in self.elements if el.ifc_type.upper() == t_upper]
