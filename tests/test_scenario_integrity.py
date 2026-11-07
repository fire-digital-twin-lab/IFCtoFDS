import json
from unittest.mock import patch
import pytest

from ifc_to_fds.adapters.jobs.runner import WorkerRunner
from ifc_to_fds.adapters.jobs.base_integrity import verify_accepted_mapping_base
from ifc_to_fds.adapters.jobs.evidence_index import write_evidence_index
from ifc_to_fds.application.services.scenario_base import (
    load_verified_base,
    load_verified_scenario_base,
)
from ifc_to_fds.domain.mapping import MappingPlan, build_mapping_plan
from ifc_to_fds.domain.validation import GateResult, GateStatus
from ifc_to_fds.fire.scenario_composer import compose_scenario, configure_scenario_time
from ifc_to_fds.fire.scenario_emitter import emit_fire_scenario
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.pipeline import convert, save_artifacts
from ifc_to_fds.results import public_result
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.parser import parse_fds
from ifc_to_fds.validation.runner import ValidationRunner


def test_scenario_worker_rejects_a_hash_without_a_verified_base(tmp_path):
    directory = tmp_path / 'job-scenario'
    directory.mkdir()
    payload = dict(mode='scenario', configuration=dict(bundle_sha256='a'*64,
                   ev_selections=[dict(preset_id='auto-nmc', position=[5,5,.75])]))
    (directory / 'request.json').write_text(json.dumps(payload))
    assert WorkerRunner.run(directory) == 1
    assert not (directory / 'scenario.fds').exists()
    assert 'Verified base bundle not found' in (directory / 'error.txt').read_text()


def _verified_bundle_for_scenario(tiny_ifc, tmp_path):
    base = tmp_path / "base"
    result = convert([str(tiny_ifc[0])], output_directory=base)
    assert result["mapping_status"] == "MAPPING_VERIFIED"
    save_artifacts(result, base / "model.fds")
    public = public_result(result, directory=base)
    (base / "result.json").write_text(json.dumps(public), encoding="utf-8")
    write_evidence_index(base, "convert", public)
    return base, result["manifest"]["bundle_sha256"]


def _verified_geom_bundle_for_scenario(tiny_ifc, tmp_path):
    base = tmp_path / "base-geom"
    result = convert(
        [str(tiny_ifc[0])],
        configuration={"all_geom": True},
        output_directory=base,
    )
    assert result["mapping_status"] == "MAPPING_VERIFIED"
    assert any(
        record["fds_representation"] == "GEOM"
        for record in result["manifest"]["records"]
    )
    save_artifacts(result, base / "model.fds")
    public = public_result(result, directory=base)
    (base / "result.json").write_text(json.dumps(public), encoding="utf-8")
    write_evidence_index(base, "convert", public)
    return base, result["manifest"]["bundle_sha256"]


def _verified_perimeter_bundle_for_scenario(tmp_path):
    import numpy as np
    import ifcopenshell.api.aggregate
    import ifcopenshell.api.context
    import ifcopenshell.api.geometry
    import ifcopenshell.api.project
    import ifcopenshell.api.root
    import ifcopenshell.api.spatial
    import ifcopenshell.api.unit

    file = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcProject", name="Scenario Collision Base"
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

    for name, y in (("South wall", 0.0), ("North wall", 10.0)):
        wall = ifcopenshell.api.root.create_entity(
            file, ifc_class="IfcWall", name=name
        )
        ifcopenshell.api.spatial.assign_container(
            file, products=[wall], relating_structure=storey
        )
        representation = ifcopenshell.api.geometry.add_wall_representation(
            file,
            context=body,
            length=10.0,
            height=3.0,
            thickness=0.2,
        )
        ifcopenshell.api.geometry.assign_representation(
            file, product=wall, representation=representation
        )
        matrix = np.eye(4)
        matrix[1, 3] = y
        ifcopenshell.api.geometry.edit_object_placement(
            file, product=wall, matrix=matrix
        )

    path = tmp_path / "scenario-collision-base.ifc"
    file.write(str(path))
    base = tmp_path / "base-collision"
    result = convert([str(path)], output_directory=base)
    assert result["mapping_status"] == "MAPPING_VERIFIED"
    save_artifacts(result, base / "model.fds")
    public = public_result(result, directory=base)
    (base / "result.json").write_text(json.dumps(public), encoding="utf-8")
    write_evidence_index(base, "convert", public)
    return base, result["manifest"]["bundle_sha256"]


def _load_sealed_base(root, digest):
    return load_verified_base(
        root, digest, verify_candidate=verify_accepted_mapping_base
    )


def test_verified_scenario_base_reconstructs_exact_emitted_geom(
    tiny_ifc, tmp_path
):
    _, digest = _verified_geom_bundle_for_scenario(tiny_ifc, tmp_path)
    base = load_verified_scenario_base(
        tmp_path,
        digest,
        verify_candidate=verify_accepted_mapping_base,
    )
    geom_records = [
        record
        for record in base.manifest.records
        if record.fds_representation == "GEOM"
    ]
    assert geom_records
    for record in geom_records:
        meshes = base.emitted_geometry.meshes_for(record.entity_key)
        primitive_ids = base.emitted_geometry.geom_primitive_ids[record.entity_key]
        assert len(meshes) == len(primitive_ids) == len(record.fds_primitive_ids)
        assert list(primitive_ids) == sorted(record.fds_primitive_ids)
        assert all(mesh.vertices and mesh.faces for mesh in meshes)


def test_scenario_worker_uses_exact_sealed_geom_for_collision(
    tiny_ifc, tmp_path
):
    _, digest = _verified_geom_bundle_for_scenario(tiny_ifc, tmp_path)
    directory = tmp_path / "job-scenario-exact-geom-collision"
    directory.mkdir()
    payload = {
        "mode": "scenario",
        "configuration": {
            "bundle_sha256": digest,
            "ev_selections": [
                {
                    "preset_id": "e-bike-lfp",
                    "position": [1.0, 0.5, 0.35],
                    "dimensions": [0.5, 0.5, 0.5],
                    "geometry_mode": "PARAMETRIC",
                    "floor_z_m": 0.0,
                    "ground_clearance_m": 0.1,
                }
            ],
        },
    }
    (directory / "request.json").write_text(json.dumps(payload), encoding="utf-8")

    assert WorkerRunner.run(directory) == 1
    error = (directory / "error.txt").read_text(encoding="utf-8")
    assert "clearance violation with verified base GEOM" in error
    assert "INCONCLUSIVE" not in error
    assert not (directory / "scenario.fds").exists()


def test_verified_base_restores_source_identity_and_placement_provenance(
    tiny_ifc, tmp_path
):
    _, digest = _verified_bundle_for_scenario(tiny_ifc, tmp_path)
    _, plan, manifest = _load_sealed_base(tmp_path, digest)

    record = next(record for record in manifest.records if record.ifc_type == "IfcWall")
    decision = plan.get_decision(record.entity_key)
    assert decision is not None
    assert decision.source_ifc_type == record.ifc_type
    assert decision.source_type_class == record.type_class
    assert decision.placement == record.placement
    assert decision.placement["status"] == "CONFIRMED"
    assert len(decision.placement["effective_world"]) == 16


def test_scenario_worker_persists_resolved_vehicle_geometry_evidence(tmp_path):
    _, digest = _verified_perimeter_bundle_for_scenario(tmp_path)
    directory = tmp_path / "job-scenario-geometry-evidence"
    directory.mkdir()
    payload = {
        "mode": "scenario",
        "configuration": {
            "bundle_sha256": digest,
            "ev_selections": [
                {
                    "preset_id": "e-bike-lfp",
                    "position": [5.0, 5.0, 0.65],
                    "dimensions": [1.8, 0.6, 1.1],
                    "geometry_mode": "PARAMETRIC",
                    "floor_z_m": 0.0,
                    "ground_clearance_m": 0.1,
                }
            ],
        },
    }
    (directory / "request.json").write_text(json.dumps(payload), encoding="utf-8")

    assert WorkerRunner.run(directory) == 0
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    geometry = result["evidence"]["vehicle_geometries"][0]
    assert geometry["mode"] == "PARAMETRIC"
    assert geometry["ground_clearance_m"] == pytest.approx(0.1)
    assert geometry["floor_z_m"] == pytest.approx(0.0)
    assert geometry["body_bounds"]["zmin"] == pytest.approx(0.1)
    assert geometry["body_bounds"]["zmax"] == pytest.approx(1.2)
    assert result["evidence"]["ev_evaluations"][0]["geometry_mode"] == "PARAMETRIC"
    collision = result["evidence"]["vehicle_collision_assessments"][0]
    assert collision["status"] == "PASS"
    assert collision["checked_base_entities"] == 2
    assert collision["checked_obst_entities"] == 2
    assert collision["checked_geom_entities"] == 0
    assert collision["minimum_aabb_clearance_m"] > 4.0


def test_verified_base_rejects_changed_fds_and_acceptance(tiny_ifc, tmp_path):
    base, digest = _verified_bundle_for_scenario(tiny_ifc, tmp_path)
    _load_sealed_base(tmp_path, digest)

    fds = base / "model.fds"
    original = fds.read_bytes()
    fds.write_bytes(original + b"\\n! changed")
    with pytest.raises(ValueError, match="Evidence file changed"):
        _load_sealed_base(tmp_path, digest)
    fds.write_bytes(original)

    manifest_path = base / "model_manifest.json"
    original_manifest = manifest_path.read_bytes()
    raw = json.loads(original_manifest.decode("utf-8"))
    raw["output_complete"] = False
    manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="not MAPPING_VERIFIED"):
        _load_sealed_base(tmp_path, digest)
    manifest_path.write_bytes(original_manifest)


def test_scenario_base_cannot_use_modified_report_or_missing_evidence_index(
    tiny_ifc, tmp_path
):
    base, digest = _verified_bundle_for_scenario(tiny_ifc, tmp_path)
    report = base / "model_acceptance_report.json"
    original = report.read_bytes()
    # A harmless JSON whitespace change is sufficient to violate the
    # sealed content-addressed evidence; prior code silently accepted it.
    report.write_bytes(original + b"\\n")
    with pytest.raises(ValueError, match="Evidence file changed"):
        _load_sealed_base(tmp_path, digest)
    report.write_bytes(original)

    index = base / "result_evidence.json"
    index.rename(base / "result_evidence.json.bak")
    with pytest.raises(ValueError, match="Missing evidence index"):
        _load_sealed_base(tmp_path, digest)


def test_scenario_base_rejects_missing_indexed_checkpoint(tiny_ifc, tmp_path):
    base, digest = _verified_bundle_for_scenario(tiny_ifc, tmp_path)
    index_path = base / "result_evidence.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["files"].pop("audit-state.json")
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="Evidence file-set differs|indexed sealed"):
        _load_sealed_base(tmp_path, digest)


def test_door_event_replaces_fixed_base_fill(box_model):
    model = box_model
    door = model.elements[0]
    door.ifc_type = 'IfcDoor'
    # Use a larger verified domain so the EV remains within the CFD model.
    from ifc_to_fds.domain.bim import BoundingBox
    model.simulation_domain = BoundingBox(xmin=-5,xmax=10,ymin=-5,ymax=10,zmin=0,zmax=5)
    base, manifest = serialize_fds(model)
    plan = build_mapping_plan(model)
    bundle = emit_fire_scenario(plan, 'a'*64, [dict(preset_id='auto-nmc',position=[5,5,.75])],
                               opening_states=[dict(entity_key=door.entity_key, state='OPEN', event_time_s=30)])
    text = compose_scenario(base, bundle, manifest)
    closures = [r for r in parse_fds(text).records if r.kind=='OBST' and r.values.get('XB')==door.bounding_box.to_xb()]
    assert len(closures)==1
    assert closures[0].values.get('CTRL_ID') or closures[0].values.get('DEVC_ID')
    assert closures[0].id == door.fds_primitive_ids[0]
    assert closures[0].values['SURF_ID'] == ['GLASS']
    assert parse_fds(base).records, 'Base mapping remains intact'


def test_both_validation_paths_keep_mesh_inconclusive_and_collect_solver_evidence(
    box_model,
):
    text = (
        "&HEAD CHID='coarse' /\n"
        "&TIME T_END=0 /\n"
        "&MESH IJK=4,4,4, XB=0,2,0,2,0,2 /\n"
        "&REAC ID='REAC_TEST', FUEL='OFFGAS', C=2.0, H=4.0, O=1.0 /\n"
        "&SURF ID='BURNER_EBIKE', HRRPUA=92.59 /\n"
        "&VENT ID='VENT_EBIKE', XB=0,1.8,0,0.6,0,0, SURF_ID='BURNER_EBIKE' /\n"
        "&TAIL /"
    )
    pair = (
        GateResult(status=GateStatus.PASS),
        GateResult(status=GateStatus.PASS),
    )
    with patch(
        "ifc_to_fds.validation.engine.solver_gates", return_value=pair
    ) as engine_solver:
        engine = run_independent_validation(box_model, text)
        engine_solver.assert_called_once()
    with patch(
        "ifc_to_fds.validation.checkers.solver.solver_gates", return_value=pair
    ) as runner_solver:
        runner = ValidationRunner().validate(box_model, text)
        runner_solver.assert_called_once()

    assert engine.gates["syntax"].status == runner.gates["syntax"].status == "PASS"
    assert (
        engine.gates["mesh_resolution"].status
        == runner.gates["mesh_resolution"].status
        == "INCONCLUSIVE"
    )
    assert engine.gates["solver"].status == runner.gates["solver"].status == "PASS"
    assert (
        engine.gates["solver"].evidence["mesh_adequacy_status"]
        == runner.gates["solver"].evidence["mesh_adequacy_status"]
        == "INCONCLUSIVE"
    )


def test_runner_preserves_effective_geometry_result(box_model):
    text, manifest = serialize_fds(box_model)
    with patch('ifc_to_fds.validation.checkers.solver.solver_gates', return_value=(
        GateResult(status=GateStatus.PASS), GateResult(status=GateStatus.FAIL, reason='Changed effective solid')
    )):
        report = ValidationRunner().validate(box_model,text,manifest)
    assert report.gates['effective_geometry'].status == 'FAIL'
    assert report.simulation_status == 'REJECTED'


def test_door_controls_do_not_collide_for_same_ifc_source(box_model):
    plan = build_mapping_plan(box_model)
    events = [dict(entity_key='a'*64 + ':' + str(step),state='OPEN',event_time_s=10) for step in (100,101)]
    original = plan.decisions[0]
    plan = MappingPlan(decisions=[
        original.model_copy(update={"entity_key": event["entity_key"], "fds_representation": "OBST"})
        for event in events
    ])
    bundle = emit_fire_scenario(plan,'b'*64,[dict(preset_id='auto-nmc',position=[5,5,.75])],opening_states=events)
    parsed = parse_fds("&HEAD CHID='doors' /\n&TIME T_END=0 /\n&MESH IJK=1,1,1, XB=0,10,0,10,0,4 /\n"+bundle.fds_fragment+'\n&TAIL /')
    assert not parsed.errors
    controls = [r.id for r in parsed.records if r.kind=='DEVC' and r.values.get("QUANTITY") == ["TIME"]]
    assert len(controls)==len(set(controls))==2


def test_unmapped_opening_cannot_emit_dangling_timer():
    with pytest.raises(ValueError, match="no mapped bounds: absent"):
        emit_fire_scenario(
            MappingPlan(), 'a' * 64,
            [dict(preset_id='e-bike-lfp', position=[1, 1, 1])],
            opening_states=[dict(entity_key='absent', state='OPEN', event_time_s=1)],
        )


@pytest.mark.parametrize("number", ["1.8E3", "1.8e3", "+1.8D3"])
def test_scenario_time_replaces_the_whole_scientific_value(number):
    text = (
        "&HEAD CHID='time', TITLE='&TIME T_END=8000 /' /\n"
        f"! &TIME T_END=9000 /\n&time\n T_END={number} /\n"
        "&MESH IJK=10,10,10, XB=0,1,0,1,0,1 /\n"
        "&RAMP ID='fire', T=1936.2, F=0 /\n&TAIL /\n"
    )
    result, end = configure_scenario_time(text, [])
    assert end == 1936.2
    assert f"&TIME T_END={end} /" in result
    assert "! &TIME T_END=9000 /" in result
    assert "TITLE='&TIME T_END=8000 /'" in result
    assert not parse_fds(result).errors


def test_scenario_time_preserves_longer_base_and_rejects_invalid_requests():
    text = "&HEAD CHID='time' /\n&TIME T_END=2E3 /\n&MESH IJK=1,1,1, XB=0,1,0,1,0,1 /\n&TAIL /"
    assert configure_scenario_time(text, [], 1000)[1] == 2000
    for invalid in (float("nan"), float("inf"), -1, True):
        with pytest.raises(ValueError):
            configure_scenario_time(text, [], invalid)
    with pytest.raises(ValueError, match="exactly one TIME"):
        configure_scenario_time(text.replace("&TAIL /", "&TIME T_END=20 /\n&TAIL /"), [])


def test_vehicle_energy_uses_serialized_burner_and_sourced_budget():
    from ifc_to_fds.fire.physics_assessment import assess_scenario_physics
    from ifc_to_fds.fire.scenario_request import EnergyBudget

    bundle = emit_fire_scenario(MappingPlan(), "a" * 64, [
        dict(preset_id="auto-nmc", position=[5, 5, .75], pack_kwh=40, peak_hrr_mw=7),
    ])
    text = ("&HEAD CHID='physics' /\n&TIME T_END=3000 /\n"
            "&MESH IJK=50,50,20, XB=0,10,0,10,0,4 /\n" + bundle.fds_fragment + "\n&TAIL /")
    no_budget = assess_scenario_physics(text, bundle, None)
    assert no_budget["energy_budget_status"] == "INCONCLUSIVE"
    assert 9010 < no_budget["nominal_energy_mj"] < 9030
    assert no_budget["hf_status"] == "NOT_MODELED"
    budget = EnergyBudget(scope="WHOLE_VEHICLE_FLEET", battery_chemical_energy_mj=1000,
                          other_vehicle_energy_mj=3000, source="Synthetic test budget")
    assert assess_scenario_physics(text, bundle, budget)["status"] == "FAIL"
    larger_budget = budget.model_copy(update={"other_vehicle_energy_mj": 10000})
    assert assess_scenario_physics(text, bundle, larger_budget)["energy_budget_status"] == "PASS"


def test_scenario_request_rejects_conflicting_sources_and_unsupported_hf():
    from ifc_to_fds.fire.scenario_request import ScenarioRequest

    payload = dict(bundle_sha256="a" * 64,
                   ev_selections=[dict(preset_id="auto-nmc", position=[5, 5, .75])])
    with pytest.raises(ValueError, match="Conflicting scenario field"):
        ScenarioRequest.model_validate(dict(payload, scenario_data={"bundle_sha256": "b" * 64}))
    with pytest.raises(ValueError, match="Quantitative HF modeling is unsupported"):
        ScenarioRequest.model_validate(dict(payload, require_quantitative_hf=True))


@pytest.mark.solver
@pytest.mark.parametrize("state", ["OPEN", "CLOSED"])
def test_fds_door_timer_changes_the_actual_fill(state, tmp_path):
    import os
    from pathlib import Path
    import re
    import subprocess

    from ifc_to_fds.domain.bim import BoundingBox
    from ifc_to_fds.domain.mapping import MappingDecision, MappingStrategy
    from ifc_to_fds.validation.solver_discovery import resolve_solver_executable

    executable = resolve_solver_executable(os.environ.get("IFCFDS_SOLVER")).executable
    assert executable is not None, "Solver suite requires FDS 6.11.1"
    executable = Path(executable)
    plan = MappingPlan(decisions=[MappingDecision(
        entity_key="door", strategy=MappingStrategy.OBST, simulation_role="DOOR",
        fds_representation="OBST",
        representation_bounds=BoundingBox(xmin=.4, xmax=.6, ymin=.2, ymax=.8, zmin=.2, zmax=.8),
    )])
    bundle = emit_fire_scenario(
        plan, "a" * 64, [dict(preset_id="e-bike-lfp", position=[2, 2, .55])],
        opening_states=[dict(entity_key="door", state=state, event_time_s=1)],
    )
    door = bundle.fds_fragment.split("! --- Opening & Boundary Controls ---", 1)[1]
    (tmp_path / "input.fds").write_bytes((
        "&HEAD CHID='door' /\n&MESH IJK=10,10,10, XB=0,1,0,1,0,1 /\n"
        "&TIME T_END=2 /\n" + door + "\n&TAIL /\n"
    ).encode())
    run = subprocess.run(
        [str(executable), "input.fds"], cwd=tmp_path, capture_output=True, text=True, timeout=45,
        env={**os.environ, "OMP_NUM_THREADS": "1",
             "PATH": str(executable.parent / "mpi") + os.pathsep + os.environ.get("PATH", "")},
    )
    log = run.stdout + run.stderr
    assert run.returncode == 0 and "completed successfully" in log and "ERROR" not in log, log
    smv = (tmp_path / "door.smv").read_text()
    events = [
        (action, float(when))
        for action, when in re.findall(r"(SHOW|HIDE)_OBST[ \t]+\d+\s+\d+[ \t]+([0-9.]+)", smv)
    ]
    before = [event for event in events if event[1] < 1]
    after = [event for event in events if event[1] >= 1]
    assert before == ([] if state == "OPEN" else [("HIDE", 0.0)]), events
    assert len(after) == 1 and after[0][0] == ("HIDE" if state == "OPEN" else "SHOW"), events
