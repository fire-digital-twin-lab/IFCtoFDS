"""Source/settings keyed converter cache. Independent audits never use this cache."""

import hashlib
import json
import os
from pathlib import Path
import uuid
import ifcopenshell
from ifc_to_fds.core.canonical import CanonicalModel, SCHEMA_VERSION, TriangleMesh
from ifc_to_fds.core.canonical import GeometryStatus
from .mesh import bounds_for_vertices
from .component_union import UNION_METHOD
from .engine import instancing_enabled, process_model_geometry, opening_diagnostic
from .storage import DiskPackage, write_package
from ifc_to_fds.diagnostics import operation


# Modules whose code decides which mesh a source element gets; editing any of them must not
# reuse meshes cached by an older version (the key would otherwise only see the IFC bytes).
FINGERPRINT_FILES = ("normalization.py", "component_union.py", "mesh.py", "boolean.py", "engine.py")
_fingerprint = None


def code_fingerprint(files=None, directory=None):
    global _fingerprint
    default = files is None and directory is None
    if default and _fingerprint:
        return _fingerprint
    digest = hashlib.sha256()
    for name in sorted(files or FINGERPRINT_FILES):
        digest.update(name.encode())
        digest.update((Path(directory) if directory else Path(__file__).parent).joinpath(name).read_bytes())
    value = digest.hexdigest()[:16]
    if default:
        _fingerprint = value
    return value


@operation("IFC_GEOMETRY")
def cached_geometry(model, file):
    directory = Path(os.environ.get("IFCFDS_GEOMETRY_CACHE", ".cache/geometry"))
    signature = dict(
        source=model.source.file_hash_sha256,
        engine=ifcopenshell.version,
        schema=SCHEMA_VERSION,
        extraction_revision="source-numerical-seams-8ulp-cap-1e-12-v5",
        component_union=UNION_METHOD,
        code=code_fingerprint(),
        iteration="local-instanced-v1" if instancing_enabled() else "world",
        world=True,
        metres=True,
        weld=True,
        deflection=0.0001,
    )
    key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    path = directory / (key + ".json")
    try:
        cached = CanonicalModel.model_validate_json(
            path.with_suffix(".inventory.json").read_text(encoding="utf-8")
        )
        package = DiskPackage(path)
        package.verify_index()
        by_key = {e.entity_key: e for e in cached.elements}
        if cached.schema_version != SCHEMA_VERSION or set(by_key) != {
            e.entity_key for e in model.elements
        }:
            raise ValueError("Cache schema/inventory mismatch")
        for e in model.elements:
            old = by_key[e.entity_key]
            entry = package["elements"][e.entity_key]
            e.mesh, e.bounding_box, e.geometry_status = (
                TriangleMesh.model_validate(entry["mesh"]) if entry["mesh"] else None,
                old.bounding_box,
                old.geometry_status,
            )
            e.bounding_box = bounds_for_vertices(e.mesh.vertices) if e.mesh else None
            e.validation_notes = old.validation_notes
            e.geometry_diagnostics = old.geometry_diagnostics
            openings = {o.opening_step_id: o for o in old.openings}
            for opening in e.openings:
                old_opening = openings[opening.opening_step_id]
                payload = entry["openings"].get(str(opening.opening_step_id))
                opening.mesh, opening.bounding_box = (
                    TriangleMesh.model_validate(payload) if payload else None,
                    old_opening.bounding_box,
                )
                opening.bounding_box = (
                    bounds_for_vertices(opening.mesh.vertices) if opening.mesh else None
                )
                opening.extraction_diagnostic = opening_diagnostic(
                    opening.mesh,
                    [old_opening.extraction_diagnostic]
                    if old_opening.extraction_diagnostic
                    else [],
                )
        model.model_bounds = cached.model_bounds
        return model
    except (OSError, ValueError, KeyError, TypeError):
        # A partial cache read must not leave stale geometry on a failed retry.
        for e in model.elements:
            e.mesh = e.bounding_box = None
            e.geometry_status = GeometryStatus.NOT_PROCESSED
            e.validation_notes = []
            for opening in e.openings:
                opening.mesh = opening.bounding_box = None
                opening.extraction_diagnostic = None
    model = process_model_geometry(model, file)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        write_package(model, path)
        temporary = directory / (key + "." + uuid.uuid4().hex + ".tmp")
        temporary.write_text(
            model.model_dump_json(
                exclude={
                    "elements": {
                        "__all__": {
                            "mesh": True,
                            "openings": {"__all__": {"mesh": True}},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        temporary.replace(path.with_suffix(".inventory.json"))
    except (OSError, ValueError):
        # A read-only cache cannot change conversion correctness.
        pass
    return model
