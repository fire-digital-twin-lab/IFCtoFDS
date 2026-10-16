"""Mapping domain models including MappingDecision and MappingPlan abstractions."""

import csv
import io
import json
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..bim.bounding_box import BoundingBox
from ..bim.model import SCHEMA_VERSION

__all__ = [
    "MappingStrategy",
    "MappingStatus",
    "MappingDecision",
    "MappingPlan",
    "ManifestRecord",
    "MappingManifest",
    "_serialize_csv_value",
]


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


def _serialize_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, list):
        if not value:
            return ""
        if all(isinstance(item, str) for item in value):
            return ";".join(value)
        return json.dumps(value, sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return value


class MappingDecision(BaseModel):
    """Explicit mapping decision for a single canonical element."""
    entity_key: str
    strategy: MappingStrategy
    simulation_role: str
    fds_representation: str
    fds_primitive_ids: List[str] = Field(default_factory=list)
    representation_bounds: Optional[BoundingBox] = None
    rationale: Optional[str] = None
    boundary_treatment: str = "NOT_APPLICABLE"


class MappingPlan(BaseModel):
    """Intermediate mapping plan decoupled from FDS serialization."""
    decisions: List[MappingDecision] = Field(default_factory=list)
    simulation_domain: Optional[BoundingBox] = None
    cell_size: float = 0.2
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_decision(self, entity_key: str) -> Optional[MappingDecision]:
        for d in self.decisions:
            if d.entity_key == entity_key:
                return d
        return None

    def sync_primitive_ids(self, model: Any) -> None:
        """Synchronize emitted primitive IDs from canonical elements into mapping decisions."""
        for elem in model.elements:
            decision = self.get_decision(elem.entity_key)
            if decision is not None:
                decision.fds_primitive_ids = list(elem.fds_primitive_ids)


class ManifestRecord(BaseModel):
    system_ids: list[str] = Field(default_factory=list)
    ports: list[dict[str, Any]] = Field(default_factory=list)
    openings: list[dict[str, Any]] = Field(default_factory=list)
    classification_evidence: list[str] = Field(default_factory=list)
    source_presence: str = "CONFIRMED"
    geometry_preservation: str = "NOT_RUN"
    simulation_role: str = "PASSIVE_OBSTACLE"
    operational_status: str = "NOT_APPLICABLE"
    fds_representation: str = "NONE"
    review_status: str = "NOT_REQUIRED"
    boundary_treatment: str = "NOT_APPLICABLE"
    boundary_policy: str | None = None
    boundary_evidence: dict[str, Any] = Field(default_factory=dict)
    representation_bounds: dict[str, float] | None = None
    source_bounds: dict[str, float] | None = None
    placement: dict[str, Any] = Field(default_factory=dict)
    building_id: str | None = None
    type_class: str | None = None
    decision: dict[str, Any] = Field(default_factory=dict)
    entity_key: str
    source_id: str
    global_id: str
    step_id: int
    ifc_type: str
    name: str
    storey: str | None = None
    systems: list[str] = Field(default_factory=list)
    scope_decision: str
    scope_rationale: str
    mapping_strategy: str
    mapping_status: str
    fds_primitive_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class MappingManifest(BaseModel):
    simulation_domain: dict[str, Any] | None = None
    geometry_package_sha256: str = ""
    mapping_acceptance: str = "INCONCLUSIVE"
    simulation_acceptance: str = "INCONCLUSIVE"
    output_complete: bool = False
    schema_version: str = SCHEMA_VERSION
    source_filename: str
    source_sha256: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    total_elements_accounted: int
    total_primitives_emitted: int
    records: list[ManifestRecord] = Field(default_factory=list)
    primitive_to_ifc: dict[str, list[str]] = Field(default_factory=dict)
    auxiliary_primitives: dict[str, str] = Field(default_factory=dict)
    fds_sha256: str = ""
    configuration: dict[str, Any] = Field(default_factory=dict)
    acceptance_status: str = "INCONCLUSIVE"

    def to_json(self, indent=2):
        return self.model_dump_json(indent=indent)

    def to_csv(self):
        output = io.StringIO()
        writer = csv.writer(output)
        fields = list(ManifestRecord.model_fields)
        writer.writerow(fields)
        for record in self.records:
            values = record.model_dump()
            writer.writerow([_serialize_csv_value(values[k]) for k in fields])
        return output.getvalue()
