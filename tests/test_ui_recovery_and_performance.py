"""Regression for source preview reuse and audit-local geometry evidence."""

from ifc_to_fds.geometry import mesh as mesh_module
import pytest


def test_evidence_reuse_is_scoped_and_detects_mesh_mutation(box_model, monkeypatch):
    calls = []
    monkeypatch.setattr(mesh_module, "has_self_intersection", lambda mesh: calls.append(1) or False)
    mesh = box_model.elements[0].mesh
    with mesh_module.mesh_evidence_scope():
        result = mesh_module.self_intersection_evidence(mesh)
        result["status"] = "CONFIRMED"
        assert mesh_module.self_intersection_evidence(mesh.model_copy(deep=True))["status"] == "CLEAN"
        assert len(calls) == 1
        mesh.vertices[0][0] += 0.001
        mesh_module.self_intersection_evidence(mesh)
        assert len(calls) == 2
    mesh_module.self_intersection_evidence(mesh)
    assert len(calls) == 3


def test_uncertain_geometry_is_retried(box_model, monkeypatch):
    def fail(mesh):
        raise RuntimeError("kernel temporarily unavailable")
    monkeypatch.setattr(mesh_module, "has_self_intersection", fail)
    with mesh_module.mesh_evidence_scope():
        assert mesh_module.self_intersection_evidence(box_model.elements[0].mesh)["status"] == "UNCERTAIN"
        monkeypatch.setattr(mesh_module, "has_self_intersection", lambda mesh: False)
        assert mesh_module.self_intersection_evidence(box_model.elements[0].mesh)["status"] == "CLEAN"


def test_preview_cache_preserves_world_geometry_and_rejects_corruption(tiny_ifc, tmp_path, monkeypatch):
    from ifc_to_fds.geometry import preview
    from ifc_to_fds.geometry.storage import DiskPackage
    monkeypatch.setenv("IFCFDS_PREVIEW_CACHE", str(tmp_path / "cache"))
    first = preview.preview_model([tiny_ifc[0]], tmp_path / "first")
    first_package = DiskPackage(tmp_path / "first/model_geometry.json")
    first_package.verify()
    assert first["status"] == "PREVIEW_ONLY" and first["verification"] == "NOT_RUN"

    def forbidden(*args, **kwargs):
        raise AssertionError("Repeated preview recalculated source shapes")
    real_iterator = preview.ifcopenshell.geom.iterator
    monkeypatch.setattr(preview.ifcopenshell.geom, "iterator", forbidden)
    second = preview.preview_model([tiny_ifc[0]], tmp_path / "second")
    assert second["preview_cache_hit"]
    assert second["bounds"] == first["bounds"]
    assert DiskPackage(tmp_path / "second/model_geometry.json").index == first_package.index

    cached_payload = next((tmp_path / "cache").glob("*/model_geometry.payloads/*.bin"))
    cached_payload.write_bytes(b"corrupt")
    monkeypatch.setattr(preview.ifcopenshell.geom, "iterator", real_iterator)
    third = preview.preview_model([tiny_ifc[0]], tmp_path / "third")
    assert not third.get("preview_cache_hit")
    DiskPackage(tmp_path / "third/model_geometry.json").verify()


@pytest.mark.parametrize("georeferenced", [False, True])
def test_independent_batch_reader_matches_individual_native_geometry(tiny_ifc, monkeypatch, georeferenced):
    from ifc_to_fds.core.inventory import extract_inventory
    from ifc_to_fds.geometry import engine
    if georeferenced:
        import numpy as np
        import ifcopenshell.api.geometry
        matrix = np.eye(4)
        angle = .27
        matrix[:2, :2] = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
        matrix[:3, 3] = [593000.1234567, 1198000.7654321, 20.35]
        ifcopenshell.api.geometry.edit_object_placement(tiny_ifc[1], product=tiny_ifc[2], matrix=matrix)
        tiny_ifc[1].write(str(tiny_ifc[0]))
    model, source = extract_inventory(str(tiny_ifc[0]))
    individual = {e.step_id: engine.extract_element_geometry(source, e, engine.create_geom_settings())
        for e in model.elements if e.has_3d_geometry}
    monkeypatch.setattr(engine, "process_model_geometry", lambda *args: (_ for _ in ()).throw(AssertionError("Converter used by auditor")))
    engine.process_reference_geometry(model, source)
    def triangles(mesh):
        return sorted(min(tuple(tuple(mesh.vertices[i]) for i in face[n:] + face[:n]) for n in range(3))
            for face in mesh.faces)
    for element in model.elements:
        if element.has_3d_geometry:
            assert triangles(element.mesh) == triangles(individual[element.step_id])


def test_independent_reader_falls_back_after_iterator_failure(tiny_ifc, monkeypatch):
    from ifc_to_fds.core.inventory import extract_inventory
    from ifc_to_fds.geometry import engine
    model, source = extract_inventory(str(tiny_ifc[0]))
    def fail(*args, **kwargs):
        raise RuntimeError("batch fixture failure")
    monkeypatch.setattr(engine.ifcopenshell.geom, "iterator", fail)
    engine.process_reference_geometry(model, source)
    physical = [e for e in model.elements if e.has_3d_geometry]
    assert physical and all(mesh_module.valid_solid(e.mesh) for e in physical)
    assert any("batch fixture failure" in note for e in physical for note in e.validation_notes)
