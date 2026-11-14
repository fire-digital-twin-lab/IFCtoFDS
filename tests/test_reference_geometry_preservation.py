"""A reference-only element (not exported to FDS) keeps its saved geometry even if the source mesh self-intersects."""

import pytest
import trimesh

from ifc_to_fds.core.federation import load_sources
from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.domain.mapping import MappingStrategy
from ifc_to_fds.geometry.package import audit_package
from ifc_to_fds.geometry.storage import read_package, write_package
from ifc_to_fds.validation.acceptance import AcceptanceReport, AuditConfig


def _overlapping_boxes():
    a = trimesh.creation.box(extents=(1, 1, 1))
    b = a.copy()
    b.apply_translation([0.25, 0.25, 0.25])
    m = trimesh.util.concatenate([a, b])
    return TriangleMesh(vertices=m.vertices.tolist(), faces=m.faces.tolist())


def _audit(tiny_ifc, tmp_path, strategy, role):
    model = load_sources([tiny_ifc[0]])
    wall = next(e for e in model.elements if e.ifc_type == "IfcWall")
    wall.mesh = _overlapping_boxes()
    wall.mapping_strategy = strategy
    wall.simulation_role = role
    path = tmp_path / "geometry.json"
    write_package(model, path)
    report = AcceptanceReport()
    audit_package(model, read_package(path), report, AuditConfig())
    return report, wall


def test_reference_only_self_intersection_does_not_fail_preservation(tiny_ifc, tmp_path):
    report, wall = _audit(tiny_ifc, tmp_path, MappingStrategy.NONE, "REFERENCE_GEOMETRY")
    assert report.gates["geometry_preservation"].status != "FAIL"
    assert wall.geometry_preservation == "PRESERVED"
    assert not [f for f in report.findings if f.element_id == wall.entity_key]


def test_emitted_element_with_self_intersection_still_fails_preservation(tiny_ifc, tmp_path):
    report, wall = _audit(tiny_ifc, tmp_path, MappingStrategy.GEOM, "PASSIVE_OBSTACLE")
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(f.element_id == wall.entity_key for f in report.findings)
