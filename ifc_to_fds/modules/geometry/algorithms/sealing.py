"""Deterministic geometry package checksums without filesystem access."""

import hashlib
import json

def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()

def seal(package):
    value = {k: v for k, v in package.items() if k != "sha256"}
    return {**value, "sha256": digest(value)}
