"""Order-insensitive identity collections; ordered numeric geometry data."""

import json


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        items = [normalize(v) for v in value]
        # Identity collections may be reordered; coordinates and matrices may not.
        if all(isinstance(v, (dict, str)) for v in value):
            return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
        return items
    return value
