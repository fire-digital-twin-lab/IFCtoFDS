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


def test_structural_completeness_checker_emits_findings_on_missing_solids(box_model):
    from ifc_to_fds.validation.checkers.structural import StructuralCompletenessChecker
    from ifc_to_fds.domain.validation.model import Severity, ValidationContext, AuditConfig

    # box_model element[0] is IFCWALL
    context = ValidationContext(
        model=box_model,
        fds_text="&HEAD TITLE='test' /\n&MESH IJK=10,10,10, XB=0,1,0,1,0,1 /\n",  # No OBST or GEOM
        manifest=None,
        config=AuditConfig(),
    )
    checker = StructuralCompletenessChecker()
    outcome = checker.check(context)
    assert outcome.result.status == "FAIL"
    assert len(outcome.findings) == 1
    assert outcome.findings[0].severity == Severity.P1
    assert outcome.findings[0].category == "structural_completeness"
    assert outcome.findings[0].element_id == box_model.elements[0].entity_key


def test_air_path_topology_checker_detects_leak_and_verifies_enclosure(box_model):
    from ifc_to_fds.validation.checkers.air_path import AirPathTopologyChecker
    from ifc_to_fds.domain.validation.model import Severity, ValidationContext, AuditConfig

    checker = AirPathTopologyChecker()

    # Case 1: Perfect match (OBST matches box model)
    xb = [0.0, 2.0, 0.0, 1.0, 0.0, 3.0]
    fds_perfect = f"&HEAD TITLE='test' /\n&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n&OBST XB={','.join(map(str, xb))}, SURF_ID='INERT' /\n"
    context_pass = ValidationContext(
        model=box_model,
        fds_text=fds_perfect,
        manifest=None,
        config=AuditConfig(),
    )
    outcome_pass = checker.check(context_pass)
    assert outcome_pass.result.status == "PASS"
    assert not outcome_pass.findings

    # Case 2: Zero emitted obstacles when enclosure expected
    context_zero = ValidationContext(
        model=box_model,
        fds_text="&HEAD TITLE='test' /\n&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n",
        manifest=None,
        config=AuditConfig(),
    )
    outcome_zero = checker.check(context_zero)
    assert outcome_zero.result.status == "FAIL"
    assert len(outcome_zero.findings) == 1
    assert outcome_zero.findings[0].severity == Severity.P1

    # Case 3: Emitted obstacle only covers a fraction of the wall (unintended breach/leak)
    # Shrunken wall leaving 75% open hole
    xb_shrunk = [0.0, 0.5, 0.0, 1.0, 0.0, 3.0]
    fds_leaked = f"&HEAD TITLE='test' /\n&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n&OBST XB={','.join(map(str, xb_shrunk))}, SURF_ID='INERT' /\n"
    context_leak = ValidationContext(
        model=box_model,
        fds_text=fds_leaked,
        manifest=None,
        config=AuditConfig(),
    )
    outcome_leak = checker.check(context_leak)
    assert outcome_leak.result.status == "FAIL"
    assert len(outcome_leak.findings) >= 1
    assert any(f.severity == Severity.P1 for f in outcome_leak.findings)


def test_air_path_excludes_non_enclosure_mep_primitives(box_model):
    from ifc_to_fds.validation.checkers.air_path import AirPathTopologyChecker
    from ifc_to_fds.domain.validation.model import ValidationContext, AuditConfig
    from ifc_to_fds.domain.bim import CanonicalElement, BoundingBox
    from ifc_to_fds.geometry.mesh import box_mesh

    wall_elem = box_model.elements[0]

    # Add a non-enclosure MEP element (duct) to the model
    duct_bbox = BoundingBox(xmin=5.0, xmax=6.0, ymin=0.0, ymax=1.0, zmin=0.0, zmax=1.0)
    duct_elem = CanonicalElement(
        entity_key="source:999",
        global_id="duct_guid_999",
        step_id=999,
        ifc_type="IfcDuctSegment",
        role="PHYSICAL",
        scope_decision="IN_SCOPE",
        mapping_strategy="OBST",
        mesh=box_mesh(duct_bbox),
        has_3d_geometry=True,
    )
    box_model.elements.append(duct_elem)

    wall_xb = "0.0,2.0,0.0,1.0,0.0,3.0"
    duct_xb = "5.0,6.0,0.0,1.0,0.0,1.0"
    fds_text = (
        "&HEAD TITLE='test' /\n"
        "&MESH IJK=10,10,10, XB=0,10,0,10,0,10 /\n"
        f"! IFC_SOURCE {{\"entity_key\": \"{wall_elem.entity_key}\"}}\n"
        f"&OBST XB={wall_xb}, SURF_ID='INERT' /\n"
        f"! IFC_SOURCE {{\"entity_key\": \"{duct_elem.entity_key}\"}}\n"
        f"&OBST XB={duct_xb}, SURF_ID='INERT' /\n"
    )

    checker = AirPathTopologyChecker()
    context = ValidationContext(
        model=box_model,
        fds_text=fds_text,
        manifest=None,
        config=AuditConfig(),
    )
    outcome = checker.check(context)
    assert outcome.result.status == "PASS"
    assert not outcome.findings
    assert outcome.result.evidence["enclosure_count"] == 1


def test_production_validation_engine_runs_air_path_gate(box_model):
    from ifc_to_fds.validation.engine import run_independent_validation
    from ifc_to_fds.domain.validation.model import GateStatus

    wall_xb = "0.0,2.0,0.0,1.0,0.0,3.0"
    wall_key = box_model.elements[0].entity_key
    fds_text = (
        "&HEAD TITLE='test' /\n"
        "&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n"
        f"! IFC_SOURCE {{\"entity_key\": \"{wall_key}\"}}\n"
        f"&OBST XB={wall_xb}, SURF_ID='INERT' /\n"
    )
    report = run_independent_validation(box_model, fds_text)

    # AirPath gate must be executed in production engine
    assert "air_path" in report.gates
    assert report.gates["air_path"].status == GateStatus.PASS
    assert "air_path" in report.metrics


def test_multi_product_geometric_batch_generation(tiny_ifc, tmp_path):
    """Verify that multiple real distinct geometric products chunk across spatial batches."""
    _, file, wall = tiny_ifc
    import ifcopenshell.api.geometry
    import numpy as np
    from ifc_to_fds.geometry.preview import preview_model

    # Create 36 distinct structural walls across a 6x6 spatial grid
    for i in range(6):
        for j in range(6):
            if i == 0 and j == 0:
                continue
            mat = np.eye(4)
            mat[0, 3] = float(i * 5.0)
            mat[1, 3] = float(j * 5.0)
            new_wall = file.create_entity(
                "IfcWall",
                GlobalId=ifcopenshell.guid.new(),
                Name=f"Grid Wall {i}_{j}",
                ObjectPlacement=wall.ObjectPlacement,
                Representation=wall.Representation,
            )
            ifcopenshell.api.geometry.edit_object_placement(file, product=new_wall, matrix=mat)

    multi_ifc = tmp_path / "multi_grid.ifc"
    file.write(str(multi_ifc))

    preview = preview_model([multi_ifc], tmp_path / "out")
    assert preview["total_elements"] >= 36
    assert preview["rendered_elements"] >= 36
    assert (tmp_path / "out" / "model_geometry.json").exists()

