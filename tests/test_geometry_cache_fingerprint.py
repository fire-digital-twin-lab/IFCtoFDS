"""The converter geometry cache must be invalidated when the code that shapes meshes changes."""

import json

import pytest

from ifc_to_fds.geometry import cache


def test_fingerprint_is_stable_and_covers_mesh_shaping_modules(tmp_path):
    first = cache.code_fingerprint()
    assert first == cache.code_fingerprint() and len(first) == 16
    for name in ("normalization.py", "component_union.py", "mesh.py", "boolean.py", "engine.py"):
        assert name in cache.FINGERPRINT_FILES


def test_fingerprint_changes_with_file_content(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    one = cache.code_fingerprint(("a.py",), tmp_path)
    (tmp_path / "a.py").write_text("x = 2")
    assert cache.code_fingerprint(("a.py",), tmp_path) != one


def test_cache_key_depends_on_fingerprint(monkeypatch, tmp_path):
    seen = []
    real = json.dumps

    def spy(obj, *a, **k):
        if isinstance(obj, dict) and "extraction_revision" in obj:
            seen.append(obj.get("code"))
        return real(obj, *a, **k)

    monkeypatch.setenv("IFCFDS_GEOMETRY_CACHE", str(tmp_path))
    monkeypatch.setattr(cache.json, "dumps", spy)
    from ifc_to_fds.core.inventory import extract_inventory
    from pathlib import Path

    model, ifc = extract_inventory(str(Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc"))
    cache.cached_geometry(model, ifc if not isinstance(ifc, str) else __import__("ifcopenshell").open(ifc))
    assert seen and seen[0] == cache.code_fingerprint()
