"""Serialized host mutations with updated checksums and independent source voids."""

import pytest
from ifc_to_fds.domain.bim import BoundingBox, OpeningReference, TriangleMesh
from ifc_to_fds.geometry.boolean import solid_boolean
from ifc_to_fds.geometry.mesh import box_mesh, as_trimesh
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.validation.engine import run_independent_validation


@pytest.mark.parametrize("mutation", ["seal", "shift", "shrink", "blocker"])
def test_opening_mutation_reports_host_gate_and_entity(box_model, mutation):
    host = box_model.elements[0]
    full = host.mesh.model_copy(deep=True)
    bounds = BoundingBox(xmin=0.5, xmax=1.5, ymin=-0.1, ymax=1.1, zmin=0.5, zmax=2)
    opening = box_mesh(bounds)

    def cut(void):
        solid = solid_boolean([as_trimesh(full), as_trimesh(void)], "difference")
        return TriangleMesh(
            vertices=solid.vertices.tolist(), faces=solid.faces.tolist()
        )

    host.mesh = cut(opening)
    host.openings = [
        OpeningReference(
            opening_global_id="void",
            opening_step_id=9,
            opening_name="Void",
            mesh=opening,
        )
    ]
    plan_mapping(box_model, force_all_geom=True)
    actual = box_model.model_copy(deep=True)
    target = actual.elements[0]
    if mutation == "seal":
        target.mesh = full
    if mutation == "shift":
        target.mesh = cut(
            box_mesh(bounds.model_copy(update={"xmin": 0.8, "xmax": 1.8}))
        )
    if mutation == "shrink":
        target.mesh = cut(
            box_mesh(bounds.model_copy(update={"xmin": 0.7, "xmax": 1.3}))
        )
    if mutation == "blocker":
        blocked = solid_boolean(
            [
                as_trimesh(target.mesh),
                as_trimesh(
                    box_mesh(
                        bounds.model_copy(
                            update={"ymin": 0.0, "ymax": 1.0, "xmax": 0.9}
                        )
                    )
                ),
            ],
            "union",
        )
        target.mesh = TriangleMesh(
            vertices=blocked.vertices.tolist(), faces=blocked.faces.tolist()
        )
    text, _ = serialize_fds(actual)
    host.fds_primitive_ids = target.fds_primitive_ids[:]
    manifest = build_manifest(
        box_model, text
    )  # current hash: semantic mutation, not stale bytes
    report = run_independent_validation(box_model, text, manifest)
    assert report.gates["openings"].status == "FAIL"
    assert any(
        f.category == "openings" and f.element_id == host.entity_key
        for f in report.findings
    )
