"""Portable result projection. Does not copy meshes into JSON inventories."""

from pathlib import Path


def sanitize_portable_paths(obj):
    if isinstance(obj, dict):
        return {
            k: (Path(v).name if k == "file_path" and isinstance(v, str) else sanitize_portable_paths(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [sanitize_portable_paths(x) for x in obj]
    return obj


def portable_inventory(model):
    return sanitize_portable_paths(model.model_dump(
        mode="json",
        exclude={"elements": {"__all__": {"mesh": True, "openings": {"__all__": {"mesh": True}}}}},
    ))
