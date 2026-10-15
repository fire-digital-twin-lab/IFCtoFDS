"""Bidirectional Mapping Manifest.

Provides complete provenance and traceability linking every source IFC
GlobalId and STEP ID to all emitted FDS primitives and vice-versa.
"""

from typing import Dict, List, Optional
import csv
import io
from pydantic import BaseModel, Field

from ifc_to_fds.core.canonical import CanonicalModel


class ManifestRecord(BaseModel):
    global_id: str
    step_id: int
    ifc_type: str
    name: str
    storey: Optional[str] = None
    systems: List[str] = Field(default_factory=list)
    mapping_strategy: str
    mapping_status: str
    fds_primitive_ids: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None


class MappingManifest(BaseModel):
    source_filename: str
    source_sha256: str
    total_elements_accounted: int
    total_primitives_emitted: int
    records: List[ManifestRecord] = Field(default_factory=list)

    # In-memory reverse lookup: primitive_id -> global_id
    primitive_to_ifc: Dict[str, str] = Field(default_factory=dict)

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def to_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "GlobalId",
            "StepId",
            "IfcType",
            "Name",
            "Storey",
            "Systems",
            "Strategy",
            "Status",
            "FdsPrimitives",
            "Rationale",
        ])
        for r in self.records:
            writer.writerow([
                r.global_id,
                r.step_id,
                r.ifc_type,
                r.name,
                r.storey or "",
                ";".join(r.systems),
                r.mapping_strategy,
                r.mapping_status,
                ";".join(r.fds_primitive_ids),
                r.rationale or "",
            ])
        return output.getvalue()


def build_manifest(model: CanonicalModel) -> MappingManifest:
    records: List[ManifestRecord] = []
    prim_to_ifc: Dict[str, str] = {}
    total_prims = 0

    for elem in model.elements:
        rec = ManifestRecord(
            global_id=elem.global_id,
            step_id=elem.step_id,
            ifc_type=elem.ifc_type,
            name=elem.name,
            storey=elem.storey,
            systems=elem.system_names,
            mapping_strategy=elem.mapping_strategy.value,
            mapping_status=elem.mapping_status.value,
            fds_primitive_ids=elem.fds_primitive_ids,
            rationale=elem.mapping_rationale,
        )
        records.append(rec)
        for prim_id in elem.fds_primitive_ids:
            prim_to_ifc[prim_id] = elem.global_id
            total_prims += 1

    return MappingManifest(
        source_filename=model.source.filename,
        source_sha256=model.source.file_hash_sha256,
        total_elements_accounted=len(model.elements),
        total_primitives_emitted=total_prims,
        records=records,
        primitive_to_ifc=prim_to_ifc,
    )
