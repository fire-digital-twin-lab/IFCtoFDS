"""Canonical BIM Model Schema.

Defines the strongly-typed intermediate data structures mediating between
raw IFC STEP entities, the geometric kernel, the MEP topological graph,
and the FDS serialized output.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MappingStatus(str, Enum):
    MATCHED = "MATCHED"
    DEVIATED = "DEVIATED"
    MISSING = "MISSING"
    SEMANTIC_ONLY = "SEMANTIC_ONLY"
    EXCLUDED_APPROVED = "EXCLUDED_APPROVED"
    UNSUPPORTED = "UNSUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    MISSING_SOURCE_DATA = "MISSING_SOURCE_DATA"


class MappingStrategy(str, Enum):
    OBST = "OBST"
    OBST_HOLE = "OBST_HOLE"
    GEOM = "GEOM"
    VOXEL = "VOXEL"
    SEMANTIC_ONLY = "SEMANTIC_ONLY"
    EXCLUDED_APPROVED = "EXCLUDED_APPROVED"


class SourceMetadata(BaseModel):
    filename: str
    file_path: str
    file_hash_sha256: str
    file_size_bytes: int
    schema_version: str  # e.g., "IFC4", "IFC2X3"
    unit_length_name: str = "METRE"
    unit_scale_to_meters: float = 1.0


class BoundingBox(BaseModel):
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float

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


class PortReference(BaseModel):
    port_global_id: str
    port_step_id: int
    name: Optional[str] = None
    flow_direction: Optional[str] = None  # SINK, SOURCE, SOURCEANDSINK, NOTDEFINED
    local_position: Optional[List[float]] = None
    connected_port_ids: List[str] = Field(default_factory=list)


class CanonicalElement(BaseModel):
    global_id: str
    step_id: int
    ifc_type: str
    name: str = ""
    tag: Optional[str] = None
    storey: Optional[str] = None
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
    mapping_status: MappingStatus = MappingStatus.MATCHED
    mapping_rationale: Optional[str] = None
    fds_primitive_ids: List[str] = Field(default_factory=list)
    validation_notes: List[str] = Field(default_factory=list)


class MEPSystem(BaseModel):
    system_id: str
    name: str
    system_type: str  # e.g., "VENTILATION", "SMOKE_EXTRACT", "FIRE_SUPPRESSION", "PLUMBING"
    element_global_ids: List[str] = Field(default_factory=list)
    is_fire_safety_critical: bool = False


class MEPConnection(BaseModel):
    connection_id: str
    source_element_id: str
    source_port_id: str
    target_element_id: str
    target_port_id: str
    relation_type: str  # "EXPLICIT_IFC", "GEOMETRIC_PROXIMITY"
    distance_meters: float = 0.0


class MEPGraph(BaseModel):
    systems: List[MEPSystem] = Field(default_factory=list)
    connections: List[MEPConnection] = Field(default_factory=list)
    isolated_element_ids: List[str] = Field(default_factory=list)


class CanonicalModel(BaseModel):
    source: SourceMetadata
    elements: List[CanonicalElement] = Field(default_factory=list)
    mep_graph: MEPGraph = Field(default_factory=MEPGraph)
    storeys: List[str] = Field(default_factory=list)
    model_bounds: Optional[BoundingBox] = None

    def get_element_by_guid(self, guid: str) -> Optional[CanonicalElement]:
        for el in self.elements:
            if el.global_id == guid:
                return el
        return None

    def get_elements_by_type(self, ifc_type: str) -> List[CanonicalElement]:
        t_upper = ifc_type.upper()
        return [el for el in self.elements if el.ifc_type.upper() == t_upper]
