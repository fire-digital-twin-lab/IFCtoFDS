import json
import pytest
from ifc_to_fds.core.canonical import (
    BoundingBox,
    StoreyReference,
    TriangleMesh,
    MappingStrategy,
)
from ifc_to_fds.mapping.policy import plan_mapping, validate_decisions
from ifc_to_fds.mapping.scope import apply_spatial_scope, SpatialScope
from ifc_to_fds.mapping.exporter import serialize_fds, compute_mesh_grid
from ifc_to_fds.mapping.manifest import build_manifest, MappingManifest
from ifc_to_fds.geometry.package import build_package, seal, audit_package
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.acceptance import AuditConfig, AcceptanceReport, GateResult
from ifc_to_fds.validation.golden import (
    create_candidate,
    golden_gate as evaluate_golden_gate,
    bundle_digest,
    inspect_case,
)
from ifc_to_fds.mep.classifier import classify_mep_element
from ifc_to_fds.geometry.mesh import box_mesh


def checked(model, text=None, package=None, configuration=None):
    if text is None:
        text, _ = serialize_fds(model)
    package = build_package(model) if package is None else package
    config = configuration or {"mep_graph": model.mep_graph.model_dump(mode="json")}
    manifest = build_manifest(model, text, config)
    manifest.geometry_package_sha256 = package["sha256"]
    report = run_independent_validation(model, text, manifest)
    audit_package(model, package, report, AuditConfig())
    report.configuration["test_serialized_fds"] = text
    return text, manifest, package, report, config


def golden_gate(report, model, manifest, package, configuration, fds_text=None):
    return evaluate_golden_gate(
        report,
        model,
        manifest,
        package,
        configuration,
        fds_text
        if fds_text is not None
        else report.configuration.get("test_serialized_fds"),
    )


def test_domain_does_not_follow_boundary_extent(box_model):
    domain = box_model.model_bounds.model_copy(deep=True)
    e = box_model.elements[0]
    e.mesh.vertices[0][2] = -2
    e.bounding_box = e.bounding_box.model_copy(update={"zmin": -2})
    box_model.simulation_domain = domain
    plan_mapping(box_model)
    text, manifest, package, report, config = checked(box_model)
    assert e.boundary_treatment == "PENDING_VALIDATION"
    assert e.mapping_strategy == "NONE"
    assert "&OBST" not in text and "&GEOM" not in text
    assert "XB=0,2,0,1,0,3" in text
    assert package["elements"][e.entity_key]["mesh"]["vertices"][0][2] == -2
    assert report.gates["boundary"].status == "INCONCLUSIVE"
    assert report.status != "MAPPING_VERIFIED"
    ijk, xb = compute_mesh_grid(domain, 0.7)
    assert xb == domain.to_xb() and ijk == [3, 2, 5]


def test_storey_interval_is_within_building(box_model):
    refs = [
        StoreyReference(
            storey_id=k, source_id="fixture", building_id=b, name=k, elevation_m=z
        )
        for k, b, z in [("A:B1", "A", 0), ("B:interleaved", "B", 1), ("A:roof", "A", 4)]
    ]
    box_model.storey_references = refs
    e = box_model.elements[0]
    e.building_id = "A"
    e.storey_id = "A:roof"
    e.mesh = box_mesh(BoundingBox(xmin=0, xmax=2, ymin=0, ymax=1, zmin=2, zmax=3))
    e.bounding_box = BoundingBox(xmin=0, xmax=2, ymin=0, ymax=1, zmin=2, zmax=3)
    apply_spatial_scope(box_model, SpatialScope(storeys=["A:B1"]))
    assert e.scope_decision == "BOUNDARY_RETAINED"


def test_proxy_and_reference_mep_do_not_become_obstacles(box_model):
    e = box_model.elements[0]
    e.ifc_type = "IfcBuildingElementProxy"
    plan_mapping(box_model, include_review_solids=True)
    text, _, package, report, _ = checked(box_model)
    assert e.review_status == "REVIEW_REQUIRED"
    assert e.simulation_role == "REFERENCE_GEOMETRY"
    assert e.fds_representation == "NONE" and "&OBST" not in text
    assert package["elements"][e.entity_key]["mesh"]
    assert report.gates["representation"].status == "INCONCLUSIVE"
    e.ifc_type = "IfcFlowSegment"
    e.type_class = "IfcPipeSegmentType"
    e.classification_evidence = ["IFC type: IfcPipeSegmentType"]
    e.mep_category = "PLUMBING"
    plan_mapping(box_model)
    _, _, _, report, _ = checked(box_model)
    assert e.review_status == "NOT_REQUIRED"
    assert report.element_statuses[e.entity_key] == "REFERENCE_PRESERVED"


def test_promotion_requires_all_factors():
    with pytest.raises(ValueError, match="all simulation relevance"):
        validate_decisions(
            {
                "x": dict(
                    action="PASSIVE_OBSTACLE",
                    policy_version="1",
                    rationale="large",
                    reviewer="engineer",
                    evidence=["review"],
                    factors={"mesh_scale": "large"},
                )
            }
        )


@pytest.mark.parametrize(
    "type_class, category",
    [("IfcDuctSegmentType", "VENTILATION"), ("IfcPipeSegmentType", "PLUMBING")],
)
def test_ifc2x3_type_class_used(type_class, category):
    assert (
        classify_mep_element("IfcFlowSegment", "unknown", type_class=type_class)[0]
        == category
    )


def test_reference_mesh_mutation_even_after_rehash(box_model):
    e = box_model.elements[0]
    e.classification_evidence = ["source MEP"]
    e.mep_category = "PLUMBING"
    plan_mapping(box_model)
    package = build_package(box_model)
    for v in package["elements"][e.entity_key]["mesh"]["vertices"]:
        v[0] += 2
    package = seal(package)
    _, _, _, report, _ = checked(box_model, package=package)
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(
        f.element_id == e.entity_key
        for f in report.findings
        if f.category == "geometry_preservation"
    )


def approve_test_fixture(directory):
    # Test ground truth only. Product code intentionally has no approve command.
    (directory / "approval.json").write_text(
        json.dumps(
            dict(
                status="APPROVED",
                bundle_sha256=bundle_digest(directory),
                reviewer="fixture author",
                rationale="analytic boxes",
                evidence=["fixture specification"],
            )
        )
    )


@pytest.fixture
def golden(box_model, tmp_path):
    e = box_model.elements[0]
    elements = []
    for index, name in enumerate(
        ("FP pipe", "duct", "fan", "ramp", "basement ceiling", "opening host"), 2
    ):
        item = e.model_copy(deep=True)
        item.entity_key = f"fixture:{index}"
        item.step_id = index
        item.global_id = f"guid-{index}"
        item.name = name
        for v in item.mesh.vertices:
            v[0] += index * 3
        item.bounding_box = item.bounding_box.model_copy(
            update={"xmin": index * 3, "xmax": index * 3 + 2}
        )
        if name in ("FP pipe", "duct", "fan"):
            item.classification_evidence = ["fixture IFC type"]
            item.mep_category = (
                "FIRE_SUPPRESSION" if name == "FP pipe" else "VENTILATION"
            )
        elements.append(item)
    box_model.elements += elements
    box_model.simulation_domain = BoundingBox(
        xmin=-1, xmax=30, ymin=-1, ymax=2, zmin=-1, zmax=4
    )
    plan_mapping(box_model)
    text, manifest, package, report, config = checked(box_model)
    directory = tmp_path / "reference"
    create_candidate(
        directory,
        box_model,
        manifest,
        package,
        report,
        config,
        report.configuration["test_serialized_fds"],
    )
    approve_test_fixture(directory)
    return box_model, directory, config


def test_golden_positive_and_draft(golden):
    model, directory, config = golden
    _, manifest, package, report, _ = checked(model)
    golden_gate(
        report, model, manifest, package, {**config, "reference_case": str(directory)}
    )
    assert report.gates["golden_reference_parity"].status == "PASS", report.model_dump()
    approval = json.loads((directory / "approval.json").read_text())
    approval["status"] = "DRAFT"
    (directory / "approval.json").write_text(json.dumps(approval))
    report = AcceptanceReport()
    golden_gate(
        report, model, manifest, package, {**config, "reference_case": str(directory)}
    )
    assert report.gates["golden_reference_parity"].status == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "mutation",
    [
        "remove FP pipe",
        "remove duct",
        "translate fan",
        "alter ramp",
        "remove basement ceiling",
        "include Level 1",
        "include sidewalk",
        "reference to passive",
        "change source",
        "invalid alias",
    ],
)
def test_golden_mutations(golden, mutation):
    model, directory, config = golden
    target = model.elements[0].entity_key
    if mutation.startswith("remove "):
        item = next(e for e in model.elements if e.name == mutation[7:])
        target = item.entity_key
        model.elements.remove(item)
    elif mutation in ("translate fan", "alter ramp", "invalid alias"):
        name = "fan" if mutation == "translate fan" else "ramp"
        item = next(e for e in model.elements if e.name == name)
        target = item.entity_key
        for v in item.mesh.vertices:
            v[0] += 2
        # Keep the mutant internally coherent so serialization can run; golden
        # must detect the altered solid rather than a stale cached source bbox.
        from ifc_to_fds.geometry.mesh import bounds_for_vertices

        item.bounding_box = bounds_for_vertices(item.mesh.vertices)
    elif mutation.startswith("include "):
        item = model.elements[0].model_copy(deep=True)
        item.entity_key = "fixture:extra"
        item.name = mutation[8:]
        item.global_id = "extra"
        item.step_id = 50
        model.elements.append(item)
        target = item.entity_key
    elif mutation == "reference to passive":
        item = next(e for e in model.elements if e.name == "duct")
        target = item.entity_key
        item.simulation_role = "PASSIVE_OBSTACLE"
        item.fds_representation = "OBST"
        item.mapping_strategy = MappingStrategy.OBST
    else:
        model.source.source_id = "different-source"
    _, manifest, package, report, _ = checked(model)
    golden_gate(
        report, model, manifest, package, {**config, "reference_case": str(directory)}
    )
    assert report.gates["golden_reference_parity"].status == "FAIL"
    assert any(
        f.category == "golden_reference_parity"
        and (f.element_id == target or mutation == "change source")
        for f in report.findings
    )


def test_golden_bundle_edit_rejected(golden):
    _, directory, _ = golden
    (directory / "scope.json").write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        inspect_case(directory)


def test_required_golden_missing_and_optional_na(box_model):
    _, manifest, package, report, config = checked(box_model)
    golden_gate(
        report, box_model, manifest, package, {**config, "profile": "research-basement"}
    )
    assert report.gates["golden_reference_parity"].status == "INCONCLUSIVE"
    golden_gate(report, box_model, manifest, package, config)
    assert report.gates["golden_reference_parity"].status == "NOT_APPLICABLE"


def test_mapping_and_simulation_levels():
    report = AcceptanceReport(
        gates={
            "geometry": GateResult(status="PASS"),
            "solver": GateResult(status="INCONCLUSIVE"),
        }
    )
    assert report.finalize().status == "MAPPING_VERIFIED"
    assert report.simulation_status == "INCONCLUSIVE"
    report.requested_level = "simulation"
    assert report.finalize().status == "INCONCLUSIVE"
    report.gates["boundary"] = GateResult(status="INCONCLUSIVE")
    assert report.finalize().mapping_status == "INCONCLUSIVE"
    report.gates["geometry"].status = "FAIL"
    assert report.finalize().status == "REJECTED"


def test_independent_file_audit_and_legacy(tiny_ifc, tmp_path):
    from ifc_to_fds.pipeline import convert, audit, save_artifacts
    from ifc_to_fds.cli import main

    path, _, _ = tiny_ifc
    result = convert([path])
    assert result["status"] == "MAPPING_VERIFIED"
    assert result["simulation_status"] == "INCONCLUSIVE"
    out = tmp_path / "output.fds"
    save_artifacts(result, out)
    assert (
        main(
            [
                "audit",
                str(path),
                "--fds",
                str(out),
                "--manifest",
                str(tmp_path / "output_manifest.json"),
                "-o",
                str(tmp_path / "audit.json"),
            ]
        )
        == 0
    )
    assert (
        json.loads((tmp_path / "audit.json").read_text())["mapping_status"]
        == "MAPPING_VERIFIED"
    )
    legacy = MappingManifest.model_validate(result["manifest"])
    legacy.schema_version = "0.3.0"
    legacy.acceptance_status = "VERIFIED"
    _, _, report = audit(
        [path], result["fds_text"], legacy, geometry_package=result["geometry_package"]
    )
    assert report.gates["schema_migration"].status == "INCONCLUSIVE"
    assert report.status == "INCONCLUSIVE"
    sim = convert([path], {"profile": "simulation"})
    assert (
        sim["mapping_status"] == "MAPPING_VERIFIED" and sim["status"] == "INCONCLUSIVE"
    )


def test_scoped_conversion_requires_independent_domain(tiny_ifc):
    from ifc_to_fds.pipeline import convert

    path, _, _ = tiny_ifc
    result = convert([path], {"scope": {"storeys": ["Ground"]}})
    assert result["status"] == "INCONCLUSIVE"
    assert result["report"]["gates"]["domain"]["status"] == "INCONCLUSIVE"
    assert "&MESH" not in result["fds_text"]


def test_golden_network_missing_edge(golden):
    from ifc_to_fds.core.canonical import MEPConnection

    model, directory, config = golden
    edge = MEPConnection(
        connection_id="edge1",
        source_element_id="fixture:2",
        target_element_id="fixture:3",
        source_port_id="p1",
        target_port_id="p2",
        relation_type="EXPLICIT_IFC",
    )
    # A test-authored baseline graph, independent of the mutated artifact.
    graph = json.loads((directory / "mep-reference.json").read_text())
    graph["connections"] = [edge.model_dump(mode="json")]
    (directory / "mep-reference.json").write_text(json.dumps(graph))
    approve_test_fixture(directory)
    _, manifest, package, report, _ = checked(model)
    golden_gate(
        report, model, manifest, package, {**config, "reference_case": str(directory)}
    )
    assert report.gates["golden_reference_parity"].status == "FAIL"
    assert any(
        f.element_id == "fixture:2" and "connection" in f.title for f in report.findings
    )


def test_golden_resealed_actual_fds(box_model, tmp_path):
    import trimesh
    from ifc_to_fds.core.canonical import OpeningReference
    from ifc_to_fds.geometry.mesh import as_trimesh

    model = box_model
    e = model.elements[0]
    solid = e.mesh.model_copy(deep=True)
    void = box_mesh(
        BoundingBox(xmin=0.5, xmax=1.5, ymin=-0.1, ymax=1.1, zmin=0.5, zmax=2)
    )
    carved = trimesh.boolean.difference(
        [as_trimesh(solid), as_trimesh(void)], engine="manifold"
    )
    e.mesh = TriangleMesh(
        vertices=carved.vertices.tolist(), faces=carved.faces.tolist()
    )
    e.openings = [
        OpeningReference(
            opening_global_id="void", opening_step_id=9, opening_name="void", mesh=void
        )
    ]
    model.simulation_domain = BoundingBox(
        xmin=-1, xmax=3, ymin=-1, ymax=2, zmin=-1, zmax=4
    )
    plan_mapping(model, force_all_geom=True)
    _, manifest, package, report, config = checked(model)
    directory = tmp_path / "opening-reference"
    create_candidate(
        directory,
        model,
        manifest,
        package,
        report,
        config,
        report.configuration["test_serialized_fds"],
    )
    approve_test_fixture(directory)
    mutant = model.model_copy(deep=True)
    mutant.elements[0].mesh = solid
    text, _ = serialize_fds(mutant)
    e.fds_primitive_ids = mutant.elements[0].fds_primitive_ids
    _, manifest, package, report, _ = checked(model, text=text)
    golden_gate(
        report, model, manifest, package, {**config, "reference_case": str(directory)}
    )
    assert report.gates["golden_reference_parity"].status == "FAIL"
    assert any(
        f.element_id == e.entity_key and "openings" in f.title
        for f in report.findings
        if f.category == "golden_reference_parity"
    )


def test_delta_is_explicit_and_does_not_waive_gate(golden):
    model, directory, config = golden
    item = next(e for e in model.elements if e.name == "duct")
    old = item.name
    item.name = "Duct reviewed label"
    delta = dict(
        status="APPROVED",
        reference_digest=bundle_digest(directory),
        changes=[
            dict(
                entity_key=item.entity_key,
                field="name",
                before=old,
                after=item.name,
                rationale="Reviewed label",
                reviewer="fixture author",
                evidence=["review record"],
            )
        ],
    )
    _, manifest, package, report, _ = checked(model)
    golden_gate(
        report,
        model,
        manifest,
        package,
        {**config, "reference_case": str(directory), "intentional_deltas": delta},
    )
    assert report.gates["golden_reference_parity"].status == "PASS"
    delta["reference_digest"] = "wrong-baseline"
    golden_gate(
        report,
        model,
        manifest,
        package,
        {**config, "reference_case": str(directory), "intentional_deltas": delta},
    )
    assert report.gates["golden_reference_parity"].status == "FAIL"


def test_alias_requires_actual_geometry_proof(golden):
    model, directory, config = golden
    aliases = [
        dict(
            entity_key="fixture:2",
            geometry_entity_key="fixture:3",
            transform=[1, 0, 0, -3, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            reviewer="fixture author",
            rationale="Identical analytic boxes",
            evidence=["geometry proof"],
        )
    ]
    (directory / "alias-decisions.json").write_text(json.dumps(aliases))
    approve_test_fixture(directory)
    _, manifest, package, report, _ = checked(model)
    golden_gate(
        report, model, manifest, package, {**config, "reference_case": str(directory)}
    )
    assert report.gates["golden_reference_parity"].status == "PASS"
    aliases[0]["transform"][3] = 0
    (directory / "alias-decisions.json").write_text(json.dumps(aliases))
    approve_test_fixture(directory)
    golden_gate(
        report, model, manifest, package, {**config, "reference_case": str(directory)}
    )
    assert report.gates["golden_reference_parity"].status == "FAIL"
    assert any(
        f.element_id == "fixture:2" and "alias_geometry" in f.title
        for f in report.findings
    )


def test_mesh_equivalence_without_vertex_or_face_order(box_model):
    import numpy as np
    from ifc_to_fds.validation.metrics import compare_solids

    reference = box_model.elements[0].mesh.model_copy(deep=True)
    # Sheared solid is not an axis-aligned box.
    for v in reference.vertices:
        v[0] += 0.4 * v[2]
    output = reference.model_copy(deep=True)
    order = np.arange(len(output.vertices))[::-1]
    output.vertices = [output.vertices[i] for i in order]
    reverse = {int(v): i for i, v in enumerate(order)}
    output.faces = [[reverse[i] for i in face] for face in reversed(output.faces)]
    metrics = compare_solids(reference, [output])
    assert metrics["surface_proven"] and metrics["surface_distance_m"] == 0


def test_scoped_explicit_domain_ignores_spatial_entities_as_obstacles(tiny_ifc):
    from ifc_to_fds.pipeline import convert

    path, _, _ = tiny_ifc
    result = convert(
        [path],
        {
            "scope": {"storeys": ["Ground"]},
            "simulation_domain": dict(
                xmin=-1, xmax=3, ymin=-1, ymax=2, zmin=-1, zmax=4
            ),
        },
    )
    assert result["status"] == "MAPPING_VERIFIED", result["report"]


def test_legacy_report_is_not_promoted():
    legacy = AcceptanceReport.model_validate(
        dict(
            schema_version="0.3.0",
            status="VERIFIED",
            gates={"geometry": {"status": "PASS"}},
        )
    )
    assert legacy.finalize().status == "INCONCLUSIVE"
    assert legacy.gates["schema_migration"].status == "INCONCLUSIVE"


def test_failed_geometry_cannot_be_declared_outside_scope(box_model):
    item = box_model.elements[0].model_copy(deep=True)
    item.entity_key = "fixture:missing"
    item.storey_id = "other"
    item.mesh = None
    item.bounding_box = None
    box_model.elements.append(item)
    apply_spatial_scope(box_model, SpatialScope(bounding_box=box_model.model_bounds))
    assert item.scope_decision == "UNRESOLVED"


def test_reference_port_coordinate_permutation_is_detected(box_model):
    from ifc_to_fds.core.canonical import PortReference

    element = box_model.elements[0]
    element.ports = [
        PortReference(
            port_global_id="port-guid",
            port_step_id=100,
            port_key="fixture:100",
            owner_key=element.entity_key,
            local_position=[0.25, 0.5, 1.0],
            world_position=[0.25, 0.5, 1.0],
        )
    ]
    plan_mapping(box_model)
    package = build_package(box_model)
    package["elements"][element.entity_key]["ports"][0]["world_position"] = [
        1.0,
        0.5,
        0.25,
    ]
    package = seal(package)
    _, _, _, report, _ = checked(box_model, package=package)
    assert report.gates["geometry_preservation"].status == "FAIL"
    assert any(
        f.element_id == element.entity_key and "ports" in f.detail
        for f in report.findings
    )


def test_source_transform_axis_permutation_is_not_equivalent(box_model):
    from ifc_to_fds.validation.golden import source_signature

    source = box_model.source.model_dump(mode="json")
    source["world_transform"][3] = 1.0
    source["world_transform"][7] = 2.0
    changed = dict(source, world_transform=list(source["world_transform"]))
    changed["world_transform"][3] = 2.0
    changed["world_transform"][7] = 1.0
    assert source_signature([source]) != source_signature([changed])


def test_equivalent_system_order_does_not_fail_mep_audit(box_model):
    from ifc_to_fds.core.canonical import MEPSystem

    box_model.mep_graph.systems = [
        MEPSystem(system_id=key, name=key, system_type="VENTILATION")
        for key in ("A", "B")
    ]
    expected = box_model.mep_graph.model_copy(deep=True)
    expected.systems.reverse()
    text, manifest = serialize_fds(box_model)
    report = run_independent_validation(
        box_model, text, manifest, expected_mep=expected
    )
    assert report.gates["mep"].status == "PASS"


def test_golden_compares_actual_fds_to_accepted_fds(box_model, tmp_path):
    box_model.simulation_domain = BoundingBox(
        xmin=-1, xmax=3, ymin=-1, ymax=2, zmin=-1, zmax=4
    )
    text, _ = serialize_fds(box_model)
    original = "XB=0,2,0,1,0,3"
    baseline = text.replace(original, "XB=0.00075,2.00075,0,1,0,3")
    actual = text.replace(original, "XB=-0.00075,1.99925,0,1,0,3")
    _, manifest, package, report, config = checked(box_model, text=baseline)
    assert report.gates["geometry"].status == "PASS"
    directory = tmp_path / "fds-baseline"
    create_candidate(directory, box_model, manifest, package, report, config, baseline)
    approve_test_fixture(directory)
    _, manifest, package, report, _ = checked(box_model, text=actual)
    assert (
        report.gates["geometry"].status == "PASS"
    )  # Both within IFC tolerance independently.
    golden_gate(
        report,
        box_model,
        manifest,
        package,
        {**config, "reference_case": str(directory)},
        actual,
    )
    assert report.gates["golden_reference_parity"].status == "FAIL"
    assert any(
        f.element_id == "fixture:1" and "golden_fds_geometry" in f.title
        for f in report.findings
    )


def test_manual_fds_import_stays_a_draft(tiny_ifc, tmp_path):
    from ifc_to_fds.pipeline import convert, save_artifacts
    from ifc_to_fds.cli import main
    from ifc_to_fds.validation.golden import inspect_case

    path, _, _ = tiny_ifc
    result = convert([path])
    fds = tmp_path / "reviewed.fds"
    save_artifacts(result, fds)
    config = tmp_path / "config.json"
    config.write_text("{}")
    directory = tmp_path / "manual-candidate"
    assert (
        main(
            [
                "reference-candidate",
                str(path),
                "--config",
                str(config),
                "--reference-fds",
                str(fds),
                "--reference-manifest",
                str(tmp_path / "reviewed_manifest.json"),
                "-o",
                str(directory),
            ]
        )
        == 2
    )
    _, approval, values = inspect_case(directory)
    assert approval["status"] == "DRAFT"
    assert values["fds-geometry.json"]["complete"]
    assert values["fds-geometry.json"]["entries"]
