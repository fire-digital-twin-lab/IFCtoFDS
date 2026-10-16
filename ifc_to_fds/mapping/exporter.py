"""FDS Serializer and Syntax Emitter.

Converts Canonical BIM Model elements into standard FDS 6+ input namelists
(&HEAD, &TIME, &MESH, &SURF, &OBST, &HOLE, &GEOM) with full IFC source provenance.
"""

from typing import List, Tuple
import math
import re

from ifc_to_fds.core.canonical import (
    BoundingBox,
    CanonicalElement,
    CanonicalModel,
    MappingStrategy,
)
from .manifest import MappingManifest, build_manifest
from ifc_to_fds.geometry.mesh import (
    bounds_for_vertices,
    valid_solid,
    is_axis_aligned_box,
)
from ifc_to_fds.core.canonical import ScopeDecision
import json


def clean_fds_id(name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "")
    cleaned = cleaned.strip("._-")
    if not cleaned:
        cleaned = fallback
    return cleaned[:30]


def format_xb(xb: List[float]) -> str:
    return f"{xb[0]:.4f},{xb[1]:.4f},{xb[2]:.4f},{xb[3]:.4f},{xb[4]:.4f},{xb[5]:.4f}"


def format_source_comment(elem: CanonicalElement) -> str:
    return "! IFC_SOURCE " + json.dumps(
        dict(
            entity_key=elem.entity_key,
            source_id=elem.source_id,
            global_id=elem.global_id,
            step_id=elem.step_id,
            ifc_type=elem.ifc_type,
        ),
        ensure_ascii=True,
    )


def compute_mesh_grid(
    bounds: BoundingBox, cell_size: float = 0.2
) -> Tuple[List[int], List[float]]:
    if not math.isfinite(cell_size) or cell_size <= 0:
        raise ValueError("cell_size must be finite and positive")
    pad = 0.4
    xb = [
        math.floor((bounds.xmin - pad) / cell_size) * cell_size,
        math.ceil((bounds.xmax + pad) / cell_size) * cell_size,
        math.floor((bounds.ymin - pad) / cell_size) * cell_size,
        math.ceil((bounds.ymax + pad) / cell_size) * cell_size,
        math.floor((bounds.zmin - pad) / cell_size) * cell_size,
        math.ceil((bounds.zmax + pad) / cell_size) * cell_size,
    ]
    ijk = [
        max(1, int(round((xb[1] - xb[0]) / cell_size))),
        max(1, int(round((xb[3] - xb[2]) / cell_size))),
        max(1, int(round((xb[5] - xb[4]) / cell_size))),
    ]
    return ijk, xb


def serialize_fds(
    model: CanonicalModel,
    cell_size: float = 0.2,
) -> Tuple[str, MappingManifest]:
    """Serializes CanonicalModel into valid FDS text and generates MappingManifest."""
    if not all(e.mapping_planned for e in model.elements):
        raise ValueError("Call plan_mapping before serialization")
    lines: List[str] = []

    chid = clean_fds_id(model.source.filename.replace(".ifc", ""), "IFC_MODEL")
    lines.append(
        f"&HEAD CHID='{chid}', TITLE='IFCtoFDS conversion; see acceptance report' /"
    )
    lines.append("&TIME T_END=0.0 /")

    # MESH calculation
    active = [
        e
        for e in model.elements
        if e.scope_decision in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
        and e.mapping_strategy in (MappingStrategy.GEOM, MappingStrategy.OBST)
        and e.mesh
        and valid_solid(e.mesh)
    ]
    bounds = bounds_for_vertices([v for e in active for v in e.mesh.vertices])
    if bounds is None:
        raise ValueError("No valid export geometry in selected scope")
    model.exported_bounds = bounds
    ijk, mesh_xb = compute_mesh_grid(bounds, cell_size=cell_size)
    lines.append(f"&MESH IJK={ijk[0]},{ijk[1]},{ijk[2]}, XB={format_xb(mesh_xb)} /")
    lines.append("")

    # Default Surfaces
    lines.append("&SURF ID='CONCRETE', COLOR='GRAY', DEFAULT=.TRUE. /")
    lines.append("&SURF ID='GLASS', COLOR='SKY BLUE', TRANSPARENCY=0.5 /")
    lines.append("&SURF ID='STEEL', COLOR='DIM GRAY' /")
    lines.append("&SURF ID='WOOD', COLOR='SANDY BROWN' /")
    lines.append("")

    prim_counter = 0

    for elem in model.elements:
        elem.fds_primitive_ids.clear()
        strategy = elem.mapping_strategy
        if elem.scope_decision in (
            ScopeDecision.OUT_OF_SCOPE,
            ScopeDecision.UNRESOLVED,
        ):
            continue
        if strategy in (MappingStrategy.GEOM, MappingStrategy.OBST) and (
            not elem.mesh or not valid_solid(elem.mesh)
        ):
            continue
        if strategy in (MappingStrategy.VOXEL, MappingStrategy.OBST_HOLE):
            raise ValueError(f"Unverified mapping strategy: {strategy.value}")
        if strategy == MappingStrategy.OBST and not is_axis_aligned_box(elem.mesh):
            raise ValueError(f"OBST lacks geometric equivalence: {elem.entity_key}")
        if (
            strategy == MappingStrategy.EXCLUDED_APPROVED
            or strategy == MappingStrategy.SEMANTIC_ONLY
        ):
            continue

        if strategy == MappingStrategy.OBST and elem.bounding_box:
            prim_counter += 1
            prim_id = f"OBST_{prim_counter}_{clean_fds_id(elem.name, 'obs')}"
            elem.fds_primitive_ids.append(prim_id)

            lines.append(format_source_comment(elem))
            lines.append(
                f"&OBST ID='{prim_id}', XB={format_xb(elem.bounding_box.to_xb())}, SURF_ID='CONCRETE' /"
            )

        elif (
            strategy == MappingStrategy.GEOM
            and elem.mesh
            and elem.mesh.vertices
            and elem.mesh.faces
        ):
            prim_counter += 1
            prim_id = f"GEOM_{prim_counter}_{clean_fds_id(elem.name, 'geom')}"
            elem.fds_primitive_ids.append(prim_id)

            verts_str = ",\n      ".join(
                f"{v[0]:.4f},{v[1]:.4f},{v[2]:.4f}" for v in elem.mesh.vertices
            )
            faces_str = ",\n      ".join(
                f"{f[0] + 1},{f[1] + 1},{f[2] + 1},1" for f in elem.mesh.faces
            )

            lines.append(format_source_comment(elem))
            lines.append(f"&GEOM ID='{prim_id}', SURF_ID='CONCRETE',")
            lines.append(f"      VERTS={verts_str},")
            lines.append(f"      FACES={faces_str} /")

    lines.append("")
    lines.append("&TAIL /")
    lines.append("")

    manifest = build_manifest(model, "\n".join(lines))
    return "\n".join(lines), manifest
