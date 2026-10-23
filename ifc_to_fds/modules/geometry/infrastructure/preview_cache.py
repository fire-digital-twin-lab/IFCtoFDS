"""Content-addressed display cache. Never consumed by conversion or audit."""

import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

import ifcopenshell

from ifc_to_fds.modules.geometry.application.package_service import seal
from ifc_to_fds.modules.geometry.infrastructure.payload_store import DiskPackage, file_hash, payload_dir


def cache_path(model):
    signature = [model.source.file_hash_sha256, ifcopenshell.version, "preview-local-5mm-v1"]
    key = hashlib.sha256(json.dumps(signature).encode()).hexdigest()
    return Path(os.getenv("IFCFDS_PREVIEW_CACHE", ".cache/preview")) / key


def copy_preview(source, destination):
    package = DiskPackage(source / "model_geometry.json")
    package.verify_index()
    target = payload_dir(destination / "model_geometry.json")
    target.mkdir(parents=True, exist_ok=True)
    for entry in package.index["elements"].values():
        ref = entry.get("mesh")
        if ref is None:
            continue
        key = ref["payload"]
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Invalid preview payload")
        path = payload_dir(package.path) / (key + ".bin")
        if path.stat().st_size != ref["byte_length"] or file_hash(path) != key:
            raise ValueError("Corrupted preview payload")
        shutil.copyfile(path, target / path.name)
    for name in ("model_geometry.json", "model_mep_graph.json"):
        shutil.copyfile(source / name, destination / name)


def read_preview(model, directory):
    source = cache_path(model)
    try:
        data = json.loads((source / "preview.json").read_text(encoding="utf-8"))
        if data.get("sha256") != seal(data)["sha256"]:
            raise ValueError("Preview metadata checksum mismatch")
        copy_preview(source, directory)
        result = data["preview"]
        result.update(status="PREVIEW_ONLY", verification="NOT_RUN", preview_cache_hit=True)
        result["sources"] = [model.source.model_dump(mode="json")]
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_preview(model, directory, result):
    target = cache_path(model)
    staging = target.with_name(target.name + "." + uuid4().hex + ".tmp")
    try:
        staging.mkdir(parents=True)
        copy_preview(directory, staging)
        (staging / "preview.json").write_text(json.dumps(seal({"preview": result})), encoding="utf-8")
        if target.exists():
            # Refresh a missing/corrupt cache without discarding other keys.
            copy_preview(staging, target)
            (staging / "preview.json").replace(target / "preview.json")
            return
        staging.replace(target)
    except (OSError, ValueError, KeyError, TypeError):
        pass  # A disabled/read-only cache cannot prevent a source preview.
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
