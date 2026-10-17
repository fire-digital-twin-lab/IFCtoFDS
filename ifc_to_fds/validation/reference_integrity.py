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
