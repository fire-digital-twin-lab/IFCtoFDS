"""Source/settings keyed converter cache. Independent audits never use this cache."""

import hashlib
import json
import os
from pathlib import Path
import uuid
import ifcopenshell
from ifc_to_fds.core.canonical import CanonicalModel, SCHEMA_VERSION
from .engine import process_model_geometry


def cached_geometry(model, file):
    directory = Path(os.environ.get("IFCFDS_GEOMETRY_CACHE", ".cache/geometry"))
    signature = dict(
        source=model.source.file_hash_sha256,
        engine=ifcopenshell.version,
        schema=SCHEMA_VERSION,
        world=True,
        metres=True,
        weld=True,
        deflection=0.0001,
    )
    key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    path = directory / (key + ".json")
    try:
        cached = CanonicalModel.model_validate_json(path.read_text(encoding="utf-8"))
        by_key = {e.entity_key: e for e in cached.elements}
        if cached.schema_version != SCHEMA_VERSION or set(by_key) != {
            e.entity_key for e in model.elements
        }:
            raise ValueError("Cache schema/inventory mismatch")
        for e in model.elements:
            old = by_key[e.entity_key]
            e.mesh, e.bounding_box, e.geometry_status = (
                old.mesh,
                old.bounding_box,
                old.geometry_status,
            )
            e.validation_notes = old.validation_notes
            openings = {o.opening_step_id: o for o in old.openings}
            for opening in e.openings:
                old_opening = openings[opening.opening_step_id]
                opening.mesh, opening.bounding_box = (
                    old_opening.mesh,
                    old_opening.bounding_box,
                )
        model.model_bounds = cached.model_bounds
        return model
    except (OSError, ValueError, KeyError):
        pass
    model = process_model_geometry(model, file)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / (key + "." + uuid.uuid4().hex + ".tmp")
        temporary.write_text(model.model_dump_json(), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        # A read-only cache cannot change conversion correctness.
        pass
    return model
