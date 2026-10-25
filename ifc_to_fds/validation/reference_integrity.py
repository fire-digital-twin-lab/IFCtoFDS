"""Shared content checks for an already-read, checksum-bound reference bundle."""

from ifc_to_fds.core.canonical import SCHEMA_VERSION, TriangleMesh
from ifc_to_fds.geometry.package import verify_package
from ifc_to_fds.mapping.manifest import MappingManifest

FIELDS = (
    "placement",
    "boundary_policy",
    "representation_bounds",
    "system_ids",
    "ports",
    "openings",
    "classification_evidence",
    "source_id",
    "global_id",
    "step_id",
    "ifc_type",
    "name",
    "type_class",
    "building_id",
    "scope_decision",
    "simulation_role",
    "operational_status",
    "fds_representation",
    "review_status",
    "boundary_treatment",
    "decision",
    "mapping_strategy",
    "fds_primitive_ids",
)


def snapshot(manifest):
    return {
        r.entity_key: {field: getattr(r, field) for field in FIELDS}
        for r in manifest.records
    }


def validate_reference(values):
    if values["acceptance-profile.json"].get("schema_version") not in (
        SCHEMA_VERSION,
        "0.4.0",
    ):
        raise ValueError("Unsupported reference schema")
    verify_package(values["geometry-package.json"])
    inventory = values["expected-inventory.json"]
    fds_evidence = values["fds-geometry.json"]
    if fds_evidence.get("schema_version") not in (
        SCHEMA_VERSION,
        "0.4.0",
    ) or not isinstance(fds_evidence.get("entries"), dict):
        raise ValueError("Invalid golden FDS geometry evidence")
    for key, meshes in fds_evidence["entries"].items():
        if key not in inventory or not isinstance(meshes, list):
            raise ValueError("Golden FDS geometry inventory conflicts")
        for mesh in meshes:
            TriangleMesh.model_validate(mesh)
    expected_snapshot = snapshot(
        MappingManifest.model_validate(values["golden-manifest.json"])
    )
    if values["golden-manifest.json"].get("schema_version") == "0.4.0":
        expected_snapshot = {
            key: {k: v for k, v in record.items() if k in inventory.get(key, {})}
            for key, record in expected_snapshot.items()
        }
    if inventory != expected_snapshot:
        raise ValueError("Reference inventory conflicts with golden manifest")
    for name in (
        "structural-reference.json",
        "hvac-reference.json",
        "fire-protection-reference.json",
        "exclusions.json",
        "boundary-elements.json",
    ):
        if any(
            k not in inventory or v != inventory[k] for k, v in values[name].items()
        ):
            raise ValueError(f"Reference projection conflicts: {name}")

    # Bidirectional reverse coverage verification: ensure required elements are not omitted
    mep_graph = values.get("mep-reference.json", {})
    systems_by_id = {}
    for s in mep_graph.get("systems", []):
        sid = s.get("system_id") if isinstance(s, dict) else None
        if not sid:
            raise ValueError("Reference projection conflicts: system entry missing system_id")
        systems_by_id[sid] = s.get("system_type", s.get("category", ""))
    for k, v in inventory.items():
        if v.get("mapping_strategy") in ("EXCLUDED_SCOPE", "EXCLUDED_APPROVED"):
            if k not in values.get("exclusions.json", {}):
                raise ValueError(f"Reference projection coverage incomplete: exclusions.json missing {k}")
        if v.get("boundary_treatment") == "PENDING_VALIDATION" or v.get("scope_decision") == "BOUNDARY_RETAINED":
            if k not in values.get("boundary-elements.json", {}):
                raise ValueError(f"Reference projection coverage incomplete: boundary-elements.json missing {k}")
        sys_ids = v.get("system_ids") or []
        unknown = [sid for sid in sys_ids if sid not in systems_by_id]
        if unknown:
            raise ValueError(f"Reference projection conflicts: unknown system_id {unknown}")
        categories = {systems_by_id[sid] for sid in sys_ids if sid in systems_by_id}
        if any(c in ("VENTILATION", "SMOKE_EXTRACT") for c in categories):
            if k not in values.get("hvac-reference.json", {}):
                raise ValueError(f"Reference projection coverage incomplete: hvac-reference.json missing {k}")
        if "FIRE_SUPPRESSION" in categories:
            if k not in values.get("fire-protection-reference.json", {}):
                raise ValueError(f"Reference projection coverage incomplete: fire-protection-reference.json missing {k}")
        if v.get("openings"):
            if k not in values.get("openings-reference.json", {}):
                raise ValueError(f"Reference projection coverage incomplete: openings-reference.json missing {k}")
