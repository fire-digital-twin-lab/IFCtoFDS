"""Versioned bidirectional provenance, finalized from audit results."""

from typing import Any
from ifc_to_fds.core.canonical import SCHEMA_VERSION
from ifc_to_fds.domain.mapping import (
    ManifestRecord,
    MappingManifest,
    _serialize_csv_value,
)

__all__ = [
    "SCHEMA_VERSION",
    "ManifestRecord",
    "MappingManifest",
    "_serialize_csv_value",
    "build_manifest",
]


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
            source_bounds=e.bounding_box.model_dump() if e.bounding_box else None,
            boundary_policy=e.boundary_policy,
            boundary_evidence=e.boundary_evidence,
            representation_bounds=e.representation_bounds.model_dump()
            if e.representation_bounds
            else None,
            placement=e.placement,
            system_ids=e.system_ids,
            classification_evidence=e.classification_evidence,
            ports=[p.model_dump(mode="json") for p in e.ports],
            openings=[
                o.model_dump(
                    mode="json",
                    exclude={
                        "mesh",
                        "bounding_box",
                        "is_subtracted",
                        "verification_status",
                    },
                )
                for o in e.openings
            ],
            **{
                field: getattr(e, field)
                for field in (
                    "source_presence",
                    "geometry_preservation",
                    "simulation_role",
                    "operational_status",
                    "fds_representation",
                    "review_status",
                    "boundary_treatment",
                    "building_id",
                    "type_class",
                    "decision",
                )
            },
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

    fds_sha256 = (
        hashlib.sha256(fds_text.encode("utf-8")).hexdigest() if fds_text else ""
    )
    domain = (
        model.simulation_domain.model_dump() if model.simulation_domain else None
    )
    manifest = MappingManifest(
        simulation_domain=domain,
        geometry_package_sha256=(configuration or {}).get(
            "geometry_package_sha256", ""
        ),
        source_filename=model.source.filename,
        source_sha256=model.source.file_hash_sha256,
        sources=[s.model_dump(mode="json") for s in model.sources or [model.source]],
        total_elements_accounted=len(records),
        total_primitives_emitted=sum(len(r.fds_primitive_ids) for r in records),
        records=records,
        primitive_to_ifc=reverse,
        fds_sha256=fds_sha256,
        configuration=configuration or {},
        mapping_acceptance=report.mapping_status.value
        if report
        else "INCONCLUSIVE",
        simulation_acceptance=report.simulation_status.value
        if report
        else "INCONCLUSIVE",
        acceptance_status=report.status.value if report else "INCONCLUSIVE",
        output_complete=report.mapping_status.value == "MAPPING_VERIFIED"
        if report
        else False,
    )
    return manifest
