import trimesh

from ifc_to_fds.domain.bim import TriangleMesh
from ifc_to_fds.domain.validation import AcceptanceReport, AuditConfig
from ifc_to_fds.modules.geometry.api import (
    as_trimesh,
    audit_package,
    build_package,
    seal,
)


def overlapping_mesh(mesh):
    left = as_trimesh(mesh)
    right = left.copy()
    right.apply_translation([0.5, 0, 0])
    combined = trimesh.util.concatenate([left, right])
    return TriangleMesh(
        vertices=combined.vertices.tolist(), faces=combined.faces.tolist()
    )


def test_self_intersecting_source_is_not_called_saved_file_corruption(box_model):
    box_model.elements[0].mesh = overlapping_mesh(box_model.elements[0].mesh)
    package = build_package(box_model)
    report = AcceptanceReport()
    audit_package(box_model, package, report, AuditConfig())
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(f.title.startswith("Invalid source solid") for f in report.findings)
    key = box_model.elements[0].entity_key
    assert (
        report.metrics[key]["preserved:solid"]["self_intersection"]["operand"]
        == "source"
    )


def test_changed_saved_mesh_is_still_reported_as_saved_failure(box_model):
    package = build_package(box_model)
    key = box_model.elements[0].entity_key
    package["elements"][key]["mesh"] = overlapping_mesh(
        box_model.elements[0].mesh
    ).model_dump(mode="json")
    report = AcceptanceReport()
    audit_package(box_model, seal(package), report, AuditConfig())
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(f.title.startswith("Invalid saved solid") for f in report.findings)
    assert report.metrics[key]["preserved:solid"]["self_intersection"][
        "operand"
    ].startswith("output:")
