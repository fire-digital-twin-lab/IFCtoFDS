"""Reference geometry normalization and serialization helpers."""

import hashlib
from typing import Any, Dict, List
from ifc_to_fds.runtime.normalization import normalize
from ifc_to_fds.domain.version import SCHEMA_VERSION
from ifc_to_fds.modules.fds.api import parse_fds


def source_signature(sources: List[Dict[str, Any]]) -> Any:
    """Deterministic normalized signature of source model metadata."""
    return normalize(
        [
            {
                k: s[k]
                for k in (
                    "source_id",
                    "file_hash_sha256",
                    "schema_version",
                    "unit_scale_to_meters",
                    "world_transform",
                )
            }
            for s in sources
        ]
    )


def serialized_geometry(text: str | None, manifest: Any) -> Dict[str, Any]:
    """Capture the actual FDS solids, with reviewed manifest links for legacy files."""
    if text is None:
        return dict(
            schema_version=SCHEMA_VERSION,
            complete=False,
            entries={},
            reason="No accepted/candidate FDS artifact supplied",
        )
    parsed = parse_fds(text)
    errors = [*parsed.errors, *parsed.unsupported]
    entries: Dict[str, Any] = {}
    actual_ids = set()
    for primitive in parsed.primitives:
        actual_ids.add(primitive.id)
        keys = manifest.primitive_to_ifc.get(primitive.id, [])
        source_key = primitive.source.get("entity_key")
        if len(keys) != 1 or (source_key and source_key != keys[0]):
            errors.append(f"Unresolved primitive source: {primitive.id}")
            continue
        if primitive.kind not in ("OBST", "GEOM"):
            errors.append(f"Unsupported golden primitive: {primitive.kind}")
            continue
        try:
            entries.setdefault(keys[0], []).append(
                primitive.mesh().model_dump(mode="json")
            )
        except ValueError as exc:
            errors.append(str(exc))
    if actual_ids != set(manifest.primitive_to_ifc):
        errors.append("Golden FDS primitive set conflicts with manifest")
    return dict(
        schema_version=SCHEMA_VERSION,
        complete=not errors,
        entries=entries,
        fds_sha256=hashlib.sha256(text.encode()).hexdigest(),
        errors=errors,
    )
