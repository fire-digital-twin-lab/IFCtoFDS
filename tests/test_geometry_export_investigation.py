"""Regressions found by the source geometry and export investigation."""
from pathlib import Path
import pytest
import trimesh

from ifc_to_fds.domain.bim import TriangleMesh, GeometryStatus
from ifc_to_fds.geometry.mesh import as_trimesh, self_intersection_evidence


def test_intersection_evidence_has_triangle_witness():
    one = trimesh.creation.box()
    two = trimesh.creation.box()
    two.apply_translation([0.25, 0.25, 0.25])
    mesh = trimesh.util.concatenate([one, two])
    raw = TriangleMesh(vertices=mesh.vertices.tolist(), faces=mesh.faces.tolist())
    before = raw.model_dump()
    evidence = self_intersection_evidence(raw)
    assert evidence['status'] == 'CONFIRMED'
    assert evidence['witness']['kind'] in ('TRIANGLE_CROSSING', 'COPLANAR_FACE_OVERLAP', 'COMPONENT_VOLUME_OVERLAP')
    assert raw.model_dump() == before


def test_audit_component_count_never_repairs_source(box_model, monkeypatch):
    from ifc_to_fds.validation.metrics import compare_solids
    def forbidden(*args, **kwargs):
        raise AssertionError('Auditor attempted to fill source holes')
    monkeypatch.setattr(trimesh.Trimesh, 'fill_holes', forbidden)
    mesh = box_model.elements[0].mesh
    assert self_intersection_evidence(mesh)['status'] == 'CLEAN'
    metrics = compare_solids(mesh, [mesh.model_copy(deep=True)])
    assert metrics['reference_components'] == metrics['output_components'] == 1


def test_invalid_door_is_retained_without_bounding_box_substitution(tiny_ifc, monkeypatch):
    from ifc_to_fds.core.inventory import extract_inventory
    from ifc_to_fds.geometry import engine
    model, source = extract_inventory(str(tiny_ifc[0]))
    elem = next(e for e in model.elements if e.has_3d_geometry)
    elem.ifc_type = 'IfcDoor'
    opened = as_trimesh(elem.mesh) if elem.mesh else trimesh.creation.box()
    raw = TriangleMesh(vertices=opened.vertices.tolist(), faces=opened.faces[:-1].tolist())
    class EmptyIterator:
        def initialize(self): return False
    monkeypatch.setattr(engine.ifcopenshell.geom, 'iterator', lambda *a, **kw: EmptyIterator())
    monkeypatch.setattr(engine, 'extract_element_geometry', lambda *a, **kw: raw.model_copy(deep=True))
    engine.process_model_geometry(model, source)
    assert elem.geometry_status == GeometryStatus.FAILED
    assert elem.mesh.vertices == raw.vertices and elem.mesh.faces == raw.faces
    assert elem.geometry_diagnostics['open_edges'] > 0
    assert elem.geometry_diagnostics['repair_applied'] is False


def test_inventory_records_source_representation(tiny_ifc):
    from ifc_to_fds.core.inventory import extract_inventory
    model, _ = extract_inventory(str(tiny_ifc[0]))
    elem = next(e for e in model.elements if e.has_3d_geometry)
    assert elem.source_representations
    assert elem.source_representations[0]['representation_type']
    assert elem.source_representations[0]['item_step_ids']


def snapshot(directory):
    return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}


def test_backup_failure_preserves_entire_existing_bundle(tiny_ifc, tmp_path, monkeypatch):
    from ifc_to_fds.pipeline import convert, save_artifacts
    from ifc_to_fds.adapters.storage import filesystem
    result = convert([tiny_ifc[0]], output_directory=tmp_path / 'work')
    target = tmp_path / 'target/model.fds'
    save_artifacts(result, target)
    before = snapshot(target.parent)
    original = filesystem.shutil.copytree
    def failing_backup(src, dst, *args, **kwargs):
        if any(p.startswith('.backup-') for p in Path(dst).parts):
            Path(dst).mkdir(parents=True, exist_ok=True)
            (Path(dst) / 'partial').write_bytes(b'incomplete backup')
            raise OSError('backup disk full')
        return original(src, dst, *args, **kwargs)
    monkeypatch.setattr(filesystem.shutil, 'copytree', failing_backup)
    with pytest.raises(OSError, match='backup disk full'):
        save_artifacts(result, target)
    assert snapshot(target.parent) == before


def test_failed_rollback_retains_recoverable_backup(tiny_ifc, tmp_path, monkeypatch):
    from ifc_to_fds.pipeline import convert, save_artifacts
    from ifc_to_fds.adapters.storage import filesystem
    result = convert([tiny_ifc[0]], output_directory=tmp_path / 'work')
    target = tmp_path / 'target/model.fds'
    save_artifacts(result, target)
    original_fds = target.read_bytes()
    result['fds_text'] = 'changed FDS'
    original_replace, original_copy = Path.replace, filesystem.shutil.copy2
    def fail_second_publication(src, dst):
        if src.parent.name.startswith('.staging-') and src.name.endswith('_manifest.json'):
            raise OSError('publication failure')
        return original_replace(src, dst)
    def fail_restore(src, dst, *args, **kwargs):
        if Path(src).parent.name.startswith('.backup-'):
            raise OSError('restore failure')
        return original_copy(src, dst, *args, **kwargs)
    monkeypatch.setattr(Path, 'replace', fail_second_publication)
    monkeypatch.setattr(filesystem.shutil, 'copy2', fail_restore)
    with pytest.raises(RuntimeError, match='Original backup retained at'):
        save_artifacts(result, target)
    backups = list(target.parent.glob('.backup-*'))
    assert len(backups) == 1
    assert (backups[0] / 'model.fds').read_bytes() == original_fds
    assert not list(target.parent.glob('.staging-*'))


def test_export_counts_distinguish_written_from_verified(tiny_ifc, tmp_path):
    from ifc_to_fds.pipeline import convert
    result = convert([tiny_ifc[0]], output_directory=tmp_path)
    counts = result['report']['coverage']['fds_export']
    assert counts['entities'] == counts['verified_entities'] == 1
    assert counts['primitives'] == counts['obst'] + counts['geom'] == 1
    assert not counts['comparisons_skipped_for_source_errors']


def test_cli_work_directory_does_not_overwrite_sibling_model(tiny_ifc, tmp_path):
    from ifc_to_fds.cli import main
    destination = tmp_path / 'exports'
    destination.mkdir()
    sibling = destination / 'model.fds'
    sibling.write_bytes(b'Unrelated existing model')
    assert main(['convert', str(tiny_ifc[0]), '-o', str(destination / 'chosen.fds')]) == 0
    assert sibling.read_bytes() == b'Unrelated existing model'
    assert (destination / 'chosen_geometry.zip').is_file()
    assert not list(destination.glob('.ifcfds-work-*'))
