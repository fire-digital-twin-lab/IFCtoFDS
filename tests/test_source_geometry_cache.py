import json
from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.geometry.cache import cached_geometry
from ifc_to_fds.geometry.mesh import valid_solid


def test_binary_ingestion_cache_preserves_identity_and_never_reuses_mapping(tiny_ifc, tmp_path, monkeypatch):
    from ifc_to_fds.geometry import cache
    from ifc_to_fds.mapping.policy import plan_mapping

    path, _, wall = tiny_ifc
    directory = tmp_path / "cache"
    monkeypatch.setenv("IFCFDS_GEOMETRY_CACHE", str(directory))
    model, source = extract_inventory(str(path))
    cached_geometry(model, source)
    original = next(e for e in model.elements if e.step_id == wall.id()).mesh.model_dump()
    inventories = list(directory.glob("*.inventory.json"))
    assert len(inventories) == 1
    data = json.loads(inventories[0].read_text(encoding="utf-8"))
    assert all("mesh" not in e for e in data["elements"])
    def must_reuse(*args): raise AssertionError("Unexpected geometry extraction")
    monkeypatch.setattr(cache, "process_model_geometry", must_reuse)
    second, source = extract_inventory(str(path))
    cached_geometry(second, source)
    element = next(e for e in second.elements if e.step_id == wall.id())
    assert element.mesh.vertices == original["vertices"]
    assert element.mesh.faces == original["faces"]
    assert valid_solid(element.mesh)
    element.classification_evidence = ["Current reviewed source classification"]
    plan_mapping(second)
    assert element.fds_representation == "NONE"


def test_independent_source_read_bypasses_converter_cache(tiny_ifc, monkeypatch):
    from ifc_to_fds.geometry import cache
    from ifc_to_fds.core.federation import load_sources
    def forbidden(*args): raise AssertionError("Audit used converter cache")
    monkeypatch.setattr(cache, "cached_geometry", forbidden)
    model = load_sources([str(tiny_ifc[0])], reference=True)
    assert any(e.mesh and valid_solid(e.mesh) for e in model.elements)
