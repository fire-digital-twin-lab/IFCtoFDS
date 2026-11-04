"""Pure projection of large canonical models into portable inventory metadata.

No scientific geometry or identity data is changed by this projection.
"""

from pathlib import Path
from typing import Any


def sanitize_portable_paths(obj: Any) -> Any:
    """Discard host-specific file directories while keeping source basenames."""
    if isinstance(obj, dict):
        return {
            key: (
                Path(value).name
                if key == "file_path" and isinstance(value, str)
                else sanitize_portable_paths(value)
            )
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [sanitize_portable_paths(value) for value in obj]
    return obj


def compact_inventory(model: Any) -> Any:
    """Keep the exact legacy inventory exclusion rules for meshes/openings."""
    return sanitize_portable_paths(
        model.model_dump(
            mode="json",
            exclude={
                "elements": {
                    "__all__": {
                        "mesh": True,
                        "openings": {"__all__": {"mesh": True}},
                    }
                }
            },
        )
    )
