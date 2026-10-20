"""Inspect selected IFC STEP entities without repairing or changing the source.

Run from the repository: python scripts/inspect-source-geometry.py model.ifc
    --step 123 --step 456 --output evidence.json
"""
import argparse
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom

from ifc_to_fds.core.inventory import compute_file_sha256, source_representations
from ifc_to_fds.core.units import get_length_unit_scale
from ifc_to_fds.geometry.engine import create_geom_settings, mesh_from_geometry
from ifc_to_fds.geometry.mesh import (
    as_trimesh, inspect_mesh_quality, self_intersection_evidence, valid_solid,
)


def inspect_source(path, steps):
    source = ifcopenshell.open(str(path))
    unit, scale = get_length_unit_scale(source)
    contexts = [dict(step_id=c.id(), precision_m=c.Precision * scale if c.Precision is not None else None)
                for c in source.by_type('IfcGeometricRepresentationContext')
                if c.is_a() == 'IfcGeometricRepresentationContext']
    results = []
    for step in steps:
        product = source.by_id(step)
        result = dict(step_id=step, global_id=getattr(product, 'GlobalId', None),
                      ifc_type=product.is_a(), name=getattr(product, 'Name', None),
                      representations=source_representations(product), repair_applied=False)
        settings = create_geom_settings()
        try:
            shape = ifcopenshell.geom.create_shape(settings, product)
            mesh = mesh_from_geometry(shape.geometry)
            result.update(quality=inspect_mesh_quality(mesh), vertices=len(mesh.vertices), faces=len(mesh.faces))
            parts = as_trimesh(mesh).split(only_watertight=False, repair=False)
            result['components'] = len(parts)
            result['closed_components'] = sum(p.is_volume for p in parts)
            # An open mesh's signed-volume integral is not a physical volume.
            result['volume_m3'] = float(as_trimesh(mesh).volume) if valid_solid(mesh) else None
            if valid_solid(mesh):
                evidence = self_intersection_evidence(mesh)
                result['world_intersection'] = evidence
            else:
                result['remediation'] = 'Re-export a closed oriented solid from the source family; open faces must not be filled with an automatic bounding box.'
            settings.set(settings.USE_WORLD_COORDS, False)
            local_shape = ifcopenshell.geom.create_shape(settings, product)
            local = mesh_from_geometry(local_shape.geometry)
            result['local_quality'] = inspect_mesh_quality(local)
            if valid_solid(local):
                result['local_intersection'] = self_intersection_evidence(local)
                if result.get('world_intersection', {}).get('status') == 'CONFIRMED':
                    result['remediation'] = (
                        'World-coordinate intersection is sensitive to placement rounding; inspect contacts in the source family. No tolerance-based acceptance applied.'
                        if result['local_intersection']['status'] == 'CLEAN' else
                        'Inspect the reported triangle pairs in the source family; its component surfaces intersect before world placement.'
                    )
        except Exception as exc:
            result['extraction_error'] = str(exc)
        results.append(result)
    return dict(source=Path(path).name, sha256=compute_file_sha256(path),
                ifcopenshell_version=ifcopenshell.version, deflection_m=0.0001,
                length_unit=unit, scale_to_meters=scale, representation_contexts=contexts,
                repair_applied=False, entities=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ifc', type=Path)
    parser.add_argument('--step', type=int, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect_source(args.ifc, args.step)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Inspected {len(report['entities'])} source entities: {args.output}")


if __name__ == '__main__':
    main()
