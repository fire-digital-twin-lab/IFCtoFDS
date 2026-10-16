"""Versioned bidirectional provenance, finalized from audit results."""

import csv
import io
from typing import Any
from pydantic import BaseModel, Field
from ifc_to_fds.core.canonical import SCHEMA_VERSION


class ManifestRecord(BaseModel):
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
            writer.writerow(
                [
                    ";".join(values[k]) if isinstance(values[k], list) else values[k]
                    for k in fields
                ]
            )
        return output.getvalue()


def build_manifest(model, fds_text="", configuration=None, report=None):
    import hashlib

    records = []
    reverse = {}
    for e in model.elements:
        status = (
            report.element_statuses.get(e.entity_key, e.mapping_status.value)
            if report
            else e.mapping_status.value
        )
        r = ManifestRecord(
            entity_key=e.entity_key,
            source_id=e.source_id,
            global_id=e.global_id,
            step_id=e.step_id,
            ifc_type=e.ifc_type,
            name=e.name,
            storey=e.storey,
            systems=e.system_names,
            scope_decision=e.scope_decision.value,
            scope_rationale=e.scope_rationale,
            mapping_strategy=e.mapping_strategy.value,
            mapping_status=status,
            fds_primitive_ids=e.fds_primitive_ids,
            rationale=e.mapping_rationale,
        )
        records.append(r)
        for pid in e.fds_primitive_ids:
            reverse.setdefault(pid, []).append(e.entity_key)
    return MappingManifest(
        source_filename=model.source.filename,
        source_sha256=model.source.file_hash_sha256,
        sources=[s.model_dump(mode="json") for s in model.sources or [model.source]],
        total_elements_accounted=len(records),
        total_primitives_emitted=len(reverse),
        records=records,
        primitive_to_ifc=reverse,
        fds_sha256=hashlib.sha256(fds_text.encode()).hexdigest(),
        configuration=configuration or {},
        acceptance_status=report.status.value if report else "INCONCLUSIVE",
    )
