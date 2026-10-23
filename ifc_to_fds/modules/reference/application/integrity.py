"""Shared content checks for an already-read, checksum-bound reference bundle."""

from ifc_to_fds.domain.contracts import SCHEMA_VERSION, TriangleMesh
from ifc_to_fds.modules.geometry.api import verify_package
from ifc_to_fds.modules.fds.api import MappingManifest
from ifc_to_fds.runtime.normalization import normalize
from ifc_to_fds.modules.reference.application.projections import source_signature

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
    for name, value in values.items():
        kind = list if name in ("alias-decisions.json", "review-queue.json") else dict
        if not isinstance(value, kind):
            raise ValueError(f"Invalid reference document: {name}")
        if kind is list and any(not isinstance(item, dict) for item in value):
            raise ValueError(f"Invalid reference entries: {name}")
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
    manifest = MappingManifest.model_validate(values["golden-manifest.json"])
    expected_snapshot = snapshot(manifest)
    if values["golden-manifest.json"].get("schema_version") == "0.4.0":
        expected_snapshot = {
            key: {k: v for k, v in record.items() if k in inventory.get(key, {})}
            for key, record in expected_snapshot.items()
        }
    if inventory != expected_snapshot:
        raise ValueError("Reference inventory conflicts with golden manifest")
    if values["acceptance-profile.json"]["schema_version"] != "0.4.0":
        try:
            _validate_links(values, manifest, inventory)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"Malformed reference evidence: {exc}") from exc
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
    systems_by_id = {
        s["system_id"]: s.get("system_type", s.get("category", ""))
        for s in mep_graph.get("systems", [])
    }
    for k, v in inventory.items():
        if v.get("mapping_strategy") in ("EXCLUDED_SCOPE", "EXCLUDED_APPROVED"):
            if k not in values.get("exclusions.json", {}):
                raise ValueError(f"Reference projection coverage incomplete: exclusions.json missing {k}")
        if v.get("boundary_treatment") == "PENDING_VALIDATION" or v.get("scope_decision") == "BOUNDARY_RETAINED":
            if k not in values.get("boundary-elements.json", {}):
                raise ValueError(f"Reference projection coverage incomplete: boundary-elements.json missing {k}")
        sys_ids = v.get("system_ids", [])
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


def _validate_links(values, manifest, inventory):
    """Check metadata links without treating a checksum as semantic approval."""
    if len(manifest.records) != len(inventory):
        raise ValueError("Reference inventory conflicts: duplicate entity identities")
    sources = values["sources.json"]["sources"]
    if not isinstance(sources, list) or not all(isinstance(s, dict) for s in sources):
        raise ValueError("Invalid reference sources")
    source_ids = [s["source_id"] for s in sources]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("Reference sources conflicts: duplicate source identities")
    if source_signature(sources) != source_signature(manifest.sources):
        raise ValueError("Reference sources.json conflicts with golden manifest")
    if values["scope.json"].get("simulation_domain") != manifest.simulation_domain:
        raise ValueError("Reference scope.json conflicts with golden manifest domain")

    package = values["geometry-package.json"]
    expected_sources = [{"source_id": s["source_id"], "world_transform": s["world_transform"]}
                        for s in sources]
    if normalize(package["sources"]) != normalize(expected_sources):
        raise ValueError("Reference geometry package sources conflicts with sources.json")
    if set(package["elements"]) != set(inventory):
        raise ValueError("Reference geometry package inventory conflicts with golden manifest")
    if manifest.geometry_package_sha256 and manifest.geometry_package_sha256 != package["sha256"]:
        raise ValueError("Reference geometry package checksum conflicts with golden manifest")
    for key, record in inventory.items():
        entry = package["elements"][key]
        required = {"source_id", "global_id", "placement", "ports", "mesh", "openings"}
        if not isinstance(entry, dict) or not required.issubset(entry):
            raise ValueError(f"Reference geometry package metadata conflicts: {key}")
        for field in ("source_id", "global_id", "step_id", "ifc_type", "placement", "ports",
                      "simulation_role", "scope_decision"):
            if field in entry and normalize(entry[field]) != normalize(record[field]):
                raise ValueError(f"Reference geometry package conflicts: {key}/{field}")
        expected_openings = {str(o["opening_step_id"]) for o in record["openings"]}
        if set(entry.get("openings", {})) != expected_openings:
            raise ValueError(f"Reference geometry package openings conflicts: {key}")

    expected_projection = {
        key: [dict(step_id=o["opening_step_id"], global_id=o["opening_global_id"],
                   fillings=o.get("filling_global_ids", [])) for o in record["openings"]]
        for key, record in inventory.items() if record["openings"]
    }
    if normalize(values["openings-reference.json"]) != normalize(expected_projection):
        raise ValueError("Reference projection conflicts: openings-reference.json")
    fds = values["fds-geometry.json"]
    if fds.get("fds_sha256") and fds["fds_sha256"] != manifest.fds_sha256:
        raise ValueError("Reference FDS geometry checksum conflicts with golden manifest")
    expected_solids = {r.entity_key for r in manifest.records if r.fds_primitive_ids}
    if fds.get("complete") and set(fds["entries"]) != expected_solids:
        raise ValueError("Reference FDS geometry inventory conflicts with golden manifest")
