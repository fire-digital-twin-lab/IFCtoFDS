import copy
import re
import pytest
from ifc_to_fds.core.canonical import BoundingBox
from ifc_to_fds.mapping.boundary import POLICY, finalize_boundary
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.acceptance import AuditConfig
from ifc_to_fds.geometry.package import build_package, audit_package


def boundary_model(model):
    model.simulation_domain = BoundingBox(
        xmin=0.4, xmax=4, ymin=0, ymax=4, zmin=0, zmax=4
    )
    model.domain_origin = "EXPLICIT_CONFIGURATION"
    return plan_mapping(model, boundary_policy=POLICY)


def test_source_is_retained_and_boundary_without_evidence_is_pending(box_model):
    original = copy.deepcopy(box_model.elements[0].mesh)
    model = boundary_model(box_model)
    e = model.elements[0]
    assert e.mesh == original
    assert e.representation_bounds.xmin == 0.4
    text, manifest = serialize_fds(model)
    assert "XB=0.4,4,0,4,0,4" in text
    report = run_independent_validation(model, text, manifest)
    audit_package(model, build_package(model), report, AuditConfig())
    finalize_boundary(model, report, manifest, text, AuditConfig())
    assert report.gates["geometry"].status == "PASS"
    assert report.gates["boundary"].status == "INCONCLUSIVE"
    assert e.boundary_treatment == "PENDING_VALIDATION"


@pytest.mark.parametrize(
    "xb", ["0.6,2.2,0,1,0,3", "0.4,2.2,0,1,0,3", "0.4,1.8,0,1,0,3", "-1,2,0,1,0,3"]
)
def test_mutated_boundary_primitive_reports_entity(box_model, xb):
    model = boundary_model(box_model)
    text, manifest = serialize_fds(model)
    text = re.sub(
        r"(&OBST[^/]*?XB=)[^/]*?(, SURF_ID)", lambda m: m[1] + xb + m[2], text
    )
    report = run_independent_validation(model, text, manifest)
    assert report.gates["geometry"].status == "FAIL"
    assert any(
        f.element_id == "fixture:1" and f.category == "geometry"
        for f in report.findings
    )


@pytest.mark.parametrize("kind", ["rotated", "geom", "mep", "promoted_mep", "stair"])
def test_unsupported_boundary_keeps_pending(box_model, kind):
    e = box_model.elements[0]
    if kind == "rotated":
        import numpy as np

        v = np.asarray(e.mesh.vertices)
        a = 0.5**0.5
        e.mesh.vertices = (v @ np.array([[a, -a, 0], [a, a, 0], [0, 0, 1]])).tolist()
    elif kind == "mep":
        e.ifc_type = "IfcFlowSegment"
    elif kind == "promoted_mep":
        e.system_ids = ["system"]
    elif kind == "stair":
        e.ifc_type = "IfcStair"
    model = boundary_model(box_model)
    plan_mapping(model, force_all_geom=kind == "geom", boundary_policy=POLICY)
    assert e.boundary_treatment == "PENDING_VALIDATION"
    assert e.representation_bounds is None
    assert e.fds_representation == "NONE"


@pytest.mark.parametrize(
    "source, expected",
    [
        ([-1, 1, 1, 2, 1, 2], [0, 1, 1, 2, 1, 2]),
        ([3, 5, 1, 2, 1, 2], [3, 4, 1, 2, 1, 2]),
        ([1, 2, -1, 1, 1, 2], [1, 2, 0, 1, 1, 2]),
        ([1, 2, 3, 5, 1, 2], [1, 2, 3, 4, 1, 2]),
        ([1, 2, 1, 2, -1, 1], [1, 2, 1, 2, 0, 1]),
        ([1, 2, 1, 2, 3, 5], [1, 2, 1, 2, 3, 4]),
        ([-1, 1, -1, 1, -1, 1], [0, 1, 0, 1, 0, 1]),
    ],
)
def test_analytic_source_intersections_keep_fixed_domain(box_model, source, expected):
    from ifc_to_fds.geometry.mesh import box_mesh

    keys = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    e = box_model.elements[0]
    e.bounding_box = BoundingBox(**dict(zip(keys, source)))
    e.mesh = box_mesh(e.bounding_box)
    original = copy.deepcopy(e.mesh)
    box_model.simulation_domain = BoundingBox(
        xmin=0, xmax=4, ymin=0, ymax=4, zmin=0, zmax=4
    )
    box_model.domain_origin = "EXPLICIT_CONFIGURATION"
    plan_mapping(box_model, boundary_policy=POLICY)
    assert e.mesh == original
    assert e.representation_bounds.to_xb() == expected
    text, _ = serialize_fds(box_model)
    assert "IJK=20,20,20, XB=0,4,0,4,0,4" in text
    assert e.boundary_treatment == "PENDING_VALIDATION"
