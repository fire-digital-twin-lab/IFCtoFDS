"""Behavior baseline generator for architectural refactor.

Captures semantic snapshots for cases A-F:
  A. Tiny synthetic IFC
  B. Model with opening (wall + window opening)
  C. AC20-FZK-Haus (Erdgeschoss)
  D. Fixture MEP (ports, systems, connections)
  E. Boundary OBST fixture (PRESERVE_AND_BLOCK policy)
  F. Golden reference synthetic fixture (draft candidate parity)
"""

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit

from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.geometry.engine import process_model_geometry
from ifc_to_fds.geometry.package import build_package
from ifc_to_fds.mapping.boundary import POLICY
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.pipeline import convert, save_artifacts
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.golden import create_candidate

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def create_tiny_ifc(file_path: str):
    file = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcProject", name="TinyTest"
    )
    ifcopenshell.api.unit.assign_unit(
        file, units=[ifcopenshell.api.unit.add_si_unit(file, unit_type="LENGTHUNIT")]
    )
    context = ifcopenshell.api.context.add_context(file, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        file,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )
    storey = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcBuildingStorey", name="Ground"
    )
    storey.Elevation = 0.0
    ifcopenshell.api.aggregate.assign_object(
        file, products=[storey], relating_object=project
    )
    wall = ifcopenshell.api.root.create_entity(file, ifc_class="IfcWall", name="Wall")
    ifcopenshell.api.spatial.assign_container(
        file, products=[wall], relating_structure=storey
    )
    representation = ifcopenshell.api.geometry.add_wall_representation(
        file, context=body, length=2.0, height=3.0, thickness=1.0
    )
    ifcopenshell.api.geometry.assign_representation(
        file, product=wall, representation=representation
    )
    ifcopenshell.api.geometry.edit_object_placement(file, product=wall)
    file.write(file_path)


def create_opening_ifc(file_path: str):
    file = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcProject", name="OpeningTest"
    )
    ifcopenshell.api.unit.assign_unit(
        file, units=[ifcopenshell.api.unit.add_si_unit(file, unit_type="LENGTHUNIT")]
    )
    context = ifcopenshell.api.context.add_context(file, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        file,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )
    storey = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcBuildingStorey", name="Level 1"
    )
    storey.Elevation = 0.0
    ifcopenshell.api.aggregate.assign_object(
        file, products=[storey], relating_object=project
    )
    wall = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcWall", name="WallWithOpening"
    )
    ifcopenshell.api.spatial.assign_container(
        file, products=[wall], relating_structure=storey
    )
    w_rep = ifcopenshell.api.geometry.add_wall_representation(
        file, context=body, length=4.0, height=3.0, thickness=0.3
    )
    ifcopenshell.api.geometry.assign_representation(
        file, product=wall, representation=w_rep
    )
    ifcopenshell.api.geometry.edit_object_placement(file, product=wall)

    opening = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcOpeningElement", name="DoorOpening"
    )
    o_rep = ifcopenshell.api.geometry.add_wall_representation(
        file, context=body, length=1.0, height=2.1, thickness=0.3
    )
    ifcopenshell.api.geometry.assign_representation(
        file, product=opening, representation=o_rep
    )
    ifcopenshell.api.geometry.edit_object_placement(file, product=opening)
    file.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=wall,
        RelatedOpeningElement=opening,
    )
    file.write(file_path)


def create_mep_ifc(file_path: str):
    file = ifcopenshell.file(schema="IFC2X3")
    org = file.create_entity("IfcOrganization", Name="Fixture")
    person = file.create_entity("IfcPerson", Id="fixture")
    user = file.create_entity(
        "IfcPersonAndOrganization", ThePerson=person, TheOrganization=org
    )
    app = file.create_entity(
        "IfcApplication",
        ApplicationDeveloper=org,
        Version="1",
        ApplicationFullName="Test",
        ApplicationIdentifier="TEST",
    )
    history = file.create_entity(
        "IfcOwnerHistory",
        OwningUser=user,
        OwningApplication=app,
        ChangeAction="ADDED",
        CreationDate=0,
    )

    def root(kind, **kwargs):
        return file.create_entity(
            kind, GlobalId=ifcopenshell.guid.new(), OwnerHistory=history, **kwargs
        )

    unit = file.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    project = root("IfcProject", Name="IFC2X3 fixture")
    project.UnitsInContext = file.create_entity("IfcUnitAssignment", Units=[unit])
    system = root("IfcSystem", Name="Smoke Extract")
    members = [
        root("IfcFlowSegment", Name="Duct"),
        root("IfcFlowFitting", Name="Elbow"),
    ]
    ports = []
    for member in members:
        point = file.create_entity("IfcCartesianPoint", Coordinates=(1.0, 0.0, 0.0))
        relative = file.create_entity("IfcAxis2Placement3D", Location=point)
        placement = file.create_entity("IfcLocalPlacement", RelativePlacement=relative)
        port = root(
            "IfcDistributionPort",
            Name="Port",
            FlowDirection="SOURCEANDSINK",
            ObjectPlacement=placement,
        )
        root("IfcRelConnectsPortToElement", RelatingPort=port, RelatedElement=member)
        root("IfcRelAssignsToGroup", RelatingGroup=system, RelatedObjects=[member])
        ports.append(port)
    root("IfcRelConnectsPorts", RelatingPort=ports[0], RelatedPort=ports[1])
    file.write(file_path)


def summarize_fds(fds_text: str) -> Dict[str, Any]:
    obsts = re.findall(r"&OBST\s+([^/]+)/", fds_text)
    geoms = re.findall(r"&GEOM\s+([^/]+)/", fds_text)
    meshes = re.findall(r"&MESH\s+([^/]+)/", fds_text)
    return {
        "obst_count": len(obsts),
        "geom_count": len(geoms),
        "mesh_count": len(meshes),
        "total_primitives": len(obsts) + len(geoms),
    }


def build_semantic_snapshot(case_id: str, result: Dict[str, Any], saved_dir: Path) -> Dict[str, Any]:
    inventory = result["inventory"]
    elements_summary = []
    for el in inventory.get("elements", []):
        elements_summary.append({
            "entity_key": el.get("entity_key"),
            "ifc_type": el.get("ifc_type"),
            "name": el.get("name"),
            "storey": el.get("storey"),
            "scope_decision": el.get("scope_decision"),
            "mapping_strategy": el.get("mapping_strategy"),
            "simulation_role": el.get("simulation_role"),
            "operational_status": el.get("operational_status"),
            "fds_representation": el.get("fds_representation"),
            "review_status": el.get("review_status"),
            "boundary_treatment": el.get("boundary_treatment"),
            "boundary_policy": el.get("boundary_policy"),
            "has_3d_geometry": el.get("has_3d_geometry"),
            "openings_count": len(el.get("openings", [])),
            "ports_count": len(el.get("ports", [])),
            "system_names": el.get("system_names", []),
            "fds_primitive_ids": sorted(el.get("fds_primitive_ids", [])),
        })
    elements_summary.sort(key=lambda x: str(x.get("entity_key")))

    manifest = result["manifest"]
    records_summary = []
    for r in manifest.get("records", []):
        records_summary.append({
            "entity_key": r.get("entity_key"),
            "mapping_status": r.get("mapping_status"),
            "mapping_strategy": r.get("mapping_strategy"),
            "simulation_role": r.get("simulation_role"),
            "boundary_treatment": r.get("boundary_treatment"),
            "fds_primitive_ids": sorted(r.get("fds_primitive_ids", [])),
            "openings_count": len(r.get("openings", [])),
            "ports_count": len(r.get("ports", [])),
        })
    records_summary.sort(key=lambda x: str(x.get("entity_key")))

    report = result["report"]
    gate_statuses = {k: v.get("status") for k, v in report.get("gates", {}).items()}

    findings_summary = [
        {
            "category": f.get("category"),
            "severity": f.get("severity"),
            "element_id": f.get("element_id"),
            "rule_id": f.get("rule_id"),
        }
        for f in report.get("findings", [])
    ]
    findings_summary.sort(key=lambda x: (str(x.get("category")), str(x.get("element_id")), str(x.get("rule_id"))))

    csv_file = saved_dir / "model_manifest.csv"
    csv_bytes = csv_file.read_bytes() if csv_file.is_file() else b""

    return {
        "case_id": case_id,
        "status": result["status"],
        "mapping_status": result["mapping_status"],
        "simulation_status": result["simulation_status"],
        "output_complete": result["output_complete"],
        "elements_count": len(elements_summary),
        "elements": elements_summary,
        "records_count": len(records_summary),
        "records": records_summary,
        "mep_systems_count": len(result.get("mep_graph", {}).get("systems", [])),
        "mep_connections_count": len(result.get("mep_graph", {}).get("connections", [])),
        "fds_summary": summarize_fds(result["fds_text"]),
        "gates": gate_statuses,
        "findings_count": len(findings_summary),
        "findings": findings_summary,
        "geometry_package_sha256": result.get("geometry_package", {}).get("sha256"),
        "manifest_csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
    }


def generate_all_snapshots():
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_root:
        root = Path(tmp_root)

        # Case A: Tiny synthetic IFC
        print("Generating Case A: Tiny synthetic...")
        p_a = str(root / "tiny.ifc")
        create_tiny_ifc(p_a)
        out_a = root / "out_a"
        out_a.mkdir()
        res_a = convert([p_a], output_directory=out_a)
        save_artifacts(res_a, out_a / "model.fds")
        snap_a = build_semantic_snapshot("case_a_tiny", res_a, out_a)
        (SNAPSHOT_DIR / "case_a_tiny.json").write_text(json.dumps(snap_a, indent=2), encoding="utf-8")

        # Case B: Model with opening
        print("Generating Case B: Model with opening...")
        p_b = str(root / "opening.ifc")
        create_opening_ifc(p_b)
        out_b = root / "out_b"
        out_b.mkdir()
        res_b = convert([p_b], output_directory=out_b)
        save_artifacts(res_b, out_b / "model.fds")
        snap_b = build_semantic_snapshot("case_b_opening", res_b, out_b)
        (SNAPSHOT_DIR / "case_b_opening.json").write_text(json.dumps(snap_b, indent=2), encoding="utf-8")

        # Case C: AC20-FZK-Haus (Erdgeschoss)
        print("Generating Case C: AC20-FZK-Haus (Erdgeschoss)...")
        p_c = "examples/AC20-FZK-Haus.ifc"
        out_c = root / "out_c"
        out_c.mkdir()
        res_c = convert([p_c], configuration={"scope": {"storeys": ["Erdgeschoss"]}}, output_directory=out_c)
        save_artifacts(res_c, out_c / "model.fds")
        snap_c = build_semantic_snapshot("case_c_fzk_erdgeschoss", res_c, out_c)
        (SNAPSHOT_DIR / "case_c_fzk_erdgeschoss.json").write_text(json.dumps(snap_c, indent=2), encoding="utf-8")

        # Case D: MEP fixture
        print("Generating Case D: MEP fixture...")
        p_d = str(root / "mep.ifc")
        create_mep_ifc(p_d)
        out_d = root / "out_d"
        out_d.mkdir()
        res_d = convert([p_d], output_directory=out_d)
        save_artifacts(res_d, out_d / "model.fds")
        snap_d = build_semantic_snapshot("case_d_mep", res_d, out_d)
        (SNAPSHOT_DIR / "case_d_mep.json").write_text(json.dumps(snap_d, indent=2), encoding="utf-8")

        # Case E: Boundary OBST fixture
        print("Generating Case E: Boundary fixture...")
        p_e = str(root / "boundary.ifc")
        create_tiny_ifc(p_e)
        out_e = root / "out_e"
        out_e.mkdir()
        res_e = convert(
            [p_e],
            configuration={
                "simulation_domain": {"xmin": 0.4, "xmax": 4.0, "ymin": 0.0, "ymax": 4.0, "zmin": 0.0, "zmax": 4.0},
                "boundary_policy": POLICY,
            },
            output_directory=out_e,
        )
        save_artifacts(res_e, out_e / "model.fds")
        snap_e = build_semantic_snapshot("case_e_boundary", res_e, out_e)
        (SNAPSHOT_DIR / "case_e_boundary.json").write_text(json.dumps(snap_e, indent=2), encoding="utf-8")

        # Case F: Golden reference synthetic fixture
        print("Generating Case F: Golden reference candidate...")
        p_f = str(root / "golden.ifc")
        create_tiny_ifc(p_f)
        candidate_dir = root / "golden_candidate"
        model_f, ifc_f = extract_inventory(p_f)
        model_f = process_model_geometry(model_f, ifc_f)
        plan_mapping(model_f)
        fds_f, manifest_f = serialize_fds(model_f)
        pkg_f = build_package(model_f)
        cfg_f = {"mep_graph": model_f.mep_graph.model_dump(mode="json")}
        rep_f = run_independent_validation(model_f, fds_f, manifest_f)
        create_candidate(candidate_dir, model_f, manifest_f, pkg_f, rep_f, cfg_f, fds_f)

        out_f = root / "out_f"
        out_f.mkdir()
        res_f = convert([p_f], configuration={"reference_case": str(candidate_dir)}, output_directory=out_f)
        save_artifacts(res_f, out_f / "model.fds")
        snap_f = build_semantic_snapshot("case_f_golden", res_f, out_f)
        (SNAPSHOT_DIR / "case_f_golden.json").write_text(json.dumps(snap_f, indent=2), encoding="utf-8")

    print(f"All 6 baseline snapshots successfully generated in {SNAPSHOT_DIR}")


if __name__ == "__main__":
    generate_all_snapshots()
