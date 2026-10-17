"""Regressions for source-solid retention and explicit MEP geometry export."""

from ifc_to_fds.core.canonical import OpeningReference
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation.engine import run_independent_validation


def test_missing_opening_keeps_valid_host_and_uncertain_opening(box_model):
    host = box_model.elements[0]
    host.openings = [
        OpeningReference(
            opening_global_id="void", opening_step_id=9, opening_name="Void"
        )
    ]
    original = host.mesh.model_dump()
    plan_mapping(box_model)
    assert host.mapping_strategy == "GEOM"
    text, manifest = serialize_fds(box_model)
    assert "&GEOM" in text
    assert host.mesh.model_dump() == original
    report = run_independent_validation(box_model, text, manifest)
    assert report.gates["geometry"].status == "PASS"
    assert report.gates["structural_completeness"].status == "PASS"
    assert report.gates["openings"].status == "INCONCLUSIVE"
    assert not manifest.output_complete


def test_invalid_host_is_still_blocked(box_model):
    host = box_model.elements[0]
    host.mesh.faces.pop()
    plan_mapping(box_model)
    assert host.mapping_strategy == "NONE"
    assert host.mapping_status == "UNSUPPORTED"


def test_fidelity_preserves_mep_without_enabling_operation(box_model):
    host = box_model.elements[0]
    host.ifc_type = "IfcFlowSegment"
    host.type_class = "IfcPipeSegmentType"
    host.classification_evidence = ["IFC type class: IfcPipeSegmentType"]
    plan_mapping(box_model)
    assert host.mapping_strategy == "NONE"
    plan_mapping(box_model, geometry_fidelity=True)
    assert host.simulation_role == "PASSIVE_OBSTACLE"
    assert host.operational_status == "NOT_CONFIGURED"
    text, manifest = serialize_fds(box_model)
    assert manifest.total_primitives_emitted == 1
    assert "&PART" not in text and "&HVAC" not in text


def test_fidelity_keeps_mep_proxy_shape_without_approving_review(box_model):
    e = box_model.elements[0]
    e.ifc_type = "IfcBuildingElementProxy"
    e.system_ids = ["source-system"]
    plan_mapping(box_model)
    assert e.fds_representation == "NONE"
    plan_mapping(box_model, geometry_fidelity=True)
    assert e.review_status == "REVIEW_REQUIRED"
    assert e.operational_status == "NOT_CONFIGURED"
    text, manifest = serialize_fds(box_model)
    assert manifest.total_primitives_emitted == 1
    report = run_independent_validation(box_model, text, manifest)
    assert report.gates["representation"].status == "INCONCLUSIVE"
    assert report.status != "MAPPING_VERIFIED"


def test_non_mep_proxy_still_requires_explicit_disposition(box_model):
    e = box_model.elements[0]
    e.ifc_type = "IfcBuildingElementProxy"
    plan_mapping(box_model, geometry_fidelity=True)
    assert e.fds_representation == "NONE"
    assert e.review_status == "REVIEW_REQUIRED"


def test_system_source_metadata_survives_extraction(tiny_ifc):
    import ifcopenshell
    from ifc_to_fds.core.inventory import extract_inventory
    from ifc_to_fds.mep.mep_graph import extract_mep_graph

    path, file, wall = tiny_ifc
    system = file.create_entity(
        "IfcSystem",
        GlobalId=ifcopenshell.guid.new(),
        Name="SPR 50",
        ObjectType="FP_Hệ thống chữa cháy Sprinkler",
        Description="Original source description",
    )
    file.create_entity(
        "IfcRelAssignsToGroup",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[wall],
        RelatingGroup=system,
    )
    file.write(str(path))
    model, reopened = extract_inventory(str(path))
    graph = extract_mep_graph(model, reopened).mep_graph
    saved = graph.systems[0]
    assert saved.object_type == system.ObjectType
    assert saved.description == system.Description
    assert saved.system_type == "FIRE_SUPPRESSION"
    assert any(system.ObjectType in item for item in saved.classification_evidence)


def test_exact_domain_clip_preserves_cut_wall_and_source(box_model):
    from ifc_to_fds.core.canonical import BoundingBox, TriangleMesh
    from ifc_to_fds.geometry.mesh import as_trimesh, box_mesh
    from ifc_to_fds.geometry.boolean import solid_boolean
    from ifc_to_fds.mapping.boundary import EXACT_POLICY

    wall = box_model.elements[0]
    opening = box_mesh(
        BoundingBox(xmin=0.5, xmax=1.5, ymin=-0.1, ymax=1.1, zmin=0.5, zmax=2.0)
    )
    carved = solid_boolean([as_trimesh(wall.mesh), as_trimesh(opening)], "difference")
    wall.mesh = TriangleMesh(
        vertices=carved.vertices.tolist(), faces=carved.faces.tolist()
    )
    wall.openings = [
        OpeningReference(
            opening_global_id="void",
            opening_step_id=9,
            opening_name="Void",
            mesh=opening,
        )
    ]
    original = wall.mesh.model_dump()
    box_model.simulation_domain = BoundingBox(
        xmin=0.4, xmax=1.8, ymin=0, ymax=1, zmin=0, zmax=3
    )
    box_model.domain_origin = "EXPLICIT_CONFIGURATION"
    plan_mapping(box_model, boundary_policy=EXACT_POLICY)
    assert wall.mapping_strategy == "GEOM"
    text, manifest = serialize_fds(box_model)
    report = run_independent_validation(box_model, text, manifest)
    assert report.gates["geometry"].status == "PASS"
    assert report.gates["openings"].status == "PASS"
    assert report.gates["boundary"].status == "INCONCLUSIVE"
    assert wall.mesh.model_dump() == original


def test_preview_writes_chunks_without_mutating_source(tiny_ifc, tmp_path):
    from ifc_to_fds.application.use_cases.preview_model import preview_model
    from ifc_to_fds.geometry.storage import read_package, file_hash

    path, _, wall = tiny_ifc
    before = file_hash(path)
    directory = tmp_path / "preview"
    directory.mkdir()
    result = preview_model([path], directory)
    assert result["verification"] == "NOT_RUN"
    assert result["rendered_elements"] == 1
    assert result["failed_elements"] == 0
    package = read_package(directory / "model_geometry.json")
    package.verify()
    entry = next(e for e in package.index["elements"].values() if e["mesh"])
    assert entry["step_id"] == wall.id()
    assert file_hash(path) == before


def test_reviewed_system_decision_promotes_members_once(box_model):
    import pytest
    from ifc_to_fds.domain.mep.model import MEPSystem
    from ifc_to_fds.mapping.policy import PROMOTION_FACTORS

    e = box_model.elements[0]
    e.system_ids = ["system:1"]
    box_model.mep_graph.systems = [
        MEPSystem(system_id="system:1", name="Pipes", system_type="UNRESOLVED")
    ]
    decision = dict(
        action="PASSIVE_OBSTACLE",
        policy_version="1",
        rationale="Review of source system geometry",
        reviewer="fixture",
        evidence="fixture evidence",
        factors={k: "reviewed" for k in PROMOTION_FACTORS},
    )
    plan_mapping(box_model, system_decisions={"system:1": decision})
    assert e.fds_representation == "OBST"
    assert e.review_status == "APPROVED"
    assert e.operational_status == "NOT_CONFIGURED"
    with pytest.raises(ValueError, match="unknown systems"):
        plan_mapping(box_model, system_decisions={"missing": decision})


def test_system_conflict_requires_entity_resolution(box_model):
    import pytest
    from ifc_to_fds.domain.mep.model import MEPSystem

    e = box_model.elements[0]
    e.system_ids = ["system:1", "system:2"]
    box_model.mep_graph.systems = [
        MEPSystem(system_id=s, name=s, system_type="UNRESOLVED") for s in e.system_ids
    ]
    base = dict(
        policy_version="1", rationale="Fixture", reviewer="fixture", evidence="fixture"
    )
    decisions = {
        "system:1": dict(base, action="REFERENCE_GEOMETRY"),
        "system:2": dict(base, action="EXCLUDE"),
    }
    with pytest.raises(ValueError, match="Conflicting system decisions"):
        plan_mapping(box_model, system_decisions=decisions)
    plan_mapping(
        box_model,
        system_decisions=decisions,
        decisions={e.entity_key: dict(base, action="REFERENCE_GEOMETRY")},
    )
    assert e.simulation_role == "REFERENCE_GEOMETRY"


def test_native_buffers_are_copied_once_for_large_meshes():
    from ifc_to_fds.geometry.engine import mesh_from_geometry

    class NativeBuffers:
        reads = 0

        @property
        def verts(self):
            self.reads += 1
            if self.reads > 2:
                raise RuntimeError("Repeated native buffer copying")
            return [0.0, 0.0, 0.0] * 10000

        @property
        def faces(self):
            self.reads += 1
            if self.reads > 2:
                raise RuntimeError("Repeated native buffer copying")
            return [0, 1, 2] * 10000

    native = NativeBuffers()
    mesh = mesh_from_geometry(native)
    assert len(mesh.vertices) == len(mesh.faces) == 10000
    assert native.reads == 2


def test_identical_triangle_proof_is_shared_but_not_skipped(box_model, monkeypatch):
    import pytest
    from ifc_to_fds.validation.metrics import compare_solids

    def self_intersecting(_):
        return {"status": "CONFIRMED"}

    monkeypatch.setattr(
        "ifc_to_fds.validation.metrics.self_intersection_evidence", self_intersecting
    )
    mesh = box_model.elements[0].mesh
    with pytest.raises(ValueError, match="Self-intersecting"):
        compare_solids(mesh, [mesh.model_copy(deep=True)])


def test_changed_output_cannot_reuse_source_intersection_proof(box_model, monkeypatch):
    import pytest
    from ifc_to_fds.validation.metrics import compare_solids

    calls = []

    def evidence(mesh):
        calls.append(mesh)
        return {"status": "CLEAN" if len(calls) == 1 else "CONFIRMED"}

    monkeypatch.setattr(
        "ifc_to_fds.validation.metrics.self_intersection_evidence", evidence
    )
    mesh = box_model.elements[0].mesh
    changed = mesh.model_copy(deep=True)
    changed.vertices = [[x + 0.1, y, z] for x, y, z in changed.vertices]
    with pytest.raises(ValueError, match="Self-intersecting"):
        compare_solids(mesh, [changed])
    assert len(calls) == 2


def test_rejected_source_preflight_does_not_claim_remaining_geometry_checked(
    box_model, monkeypatch
):
    from ifc_to_fds.validation.acceptance import AuditConfig
    import ifc_to_fds.validation.engine as engine

    healthy = box_model.elements[0].model_copy(deep=True)
    healthy.entity_key, healthy.step_id, healthy.global_id = "fixture:2", 2, "second"
    box_model.elements.append(healthy)
    box_model.elements[0].mesh.faces.pop()
    plan_mapping(box_model)
    text, manifest = serialize_fds(box_model)
    calls = []
    original = engine.compare_solids

    def measured(*args):
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(engine, "compare_solids", measured)
    report = engine.run_independent_validation(
        box_model, text, manifest, AuditConfig(fail_fast_on_source_errors=True)
    )
    assert report.status == "REJECTED"
    assert report.gates["geometry"].status == "FAIL"
    assert report.gates["openings"].status == "NOT_RUN"
    assert report.gates["solver"].status == "NOT_RUN"
    assert report.element_statuses[healthy.entity_key] == "INCONCLUSIVE"
    assert not calls
    full = engine.run_independent_validation(
        box_model, text, manifest, AuditConfig(fail_fast_on_source_errors=False)
    )
    assert full.status == "REJECTED"
    assert full.element_statuses[healthy.entity_key] == "MATCHED"
    assert len(calls) == 1
