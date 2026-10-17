"""FDS Serializer and Syntax Emitter.

Converts Canonical BIM Model elements into standard FDS 6+ input namelists
(&HEAD, &TIME, &MESH, &SURF, &OBST, &HOLE, &GEOM) with full IFC source provenance.
"""

from typing import List, Optional, Tuple
import math
import re
from dataclasses import dataclass
from ifc_to_fds.diagnostics import operation

from ifc_to_fds.core.canonical import (
    BoundingBox,
    CanonicalElement,
    CanonicalModel,
    MappingStrategy,
)
from ifc_to_fds.domain.mapping import MappingPlan
from .manifest import MappingManifest, build_manifest
from ifc_to_fds.geometry.mesh import (
    bounds_for_vertices,
    valid_solid,
    is_axis_aligned_box,
)
from ifc_to_fds.core.canonical import ScopeDecision
import json


@dataclass(frozen=True)
class SerializationResult:
    """Output of rendering; primitive assignments are not mapping intent."""

    fds_text: str
    manifest: MappingManifest
    primitive_assignments: dict[str, list[str]]
    exported_bounds: Optional[BoundingBox]
    domain: Optional[BoundingBox]


def clean_fds_id(name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "")
    cleaned = cleaned.strip("._-")
    if not cleaned:
        cleaned = fallback
    return cleaned[:30]


def format_xb(xb: List[float]) -> str:
    # Shortest binary64 round trip; keep integral bounds readable for legacy callers.
    return ",".join(str(int(v)) if float(v).is_integer() else repr(float(v)) for v in xb)


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
    xb = bounds.to_xb()
    ijk = [
        max(1, math.ceil((xb[1] - xb[0]) / cell_size)),
        max(1, math.ceil((xb[3] - xb[2]) / cell_size)),
        max(1, math.ceil((xb[5] - xb[4]) / cell_size)),
    ]
    return ijk, xb


def serialize_fds(
    model: CanonicalModel,
    cell_size: Optional[float] = None,
    mapping_plan: Optional[MappingPlan] = None,
) -> Tuple[str, MappingManifest]:
    """Legacy tuple API; mirrors only primitive IDs and exported bounds as outputs."""
    result = serialize_mapping(model, cell_size, mapping_plan)
    for element in model.elements:
        element.fds_primitive_ids = list(result.primitive_assignments[element.entity_key])
    model.exported_bounds = result.exported_bounds
    return result.fds_text, result.manifest


@operation("SERIALIZATION")
def serialize_mapping(model, cell_size=None, mapping_plan=None) -> SerializationResult:
    """Render a validated plan without modifying the source model or plan."""
    from ifc_to_fds.domain.mapping import build_mapping_plan
    from .plan_validation import planned_model

    if cell_size is not None and (not math.isfinite(cell_size) or cell_size <= 0):
        raise ValueError("cell_size must be finite and positive")
    if mapping_plan is None:
        mapping_plan = build_mapping_plan(model, cell_size=0.2 if cell_size is None else cell_size)
    elif cell_size is not None and cell_size != mapping_plan.cell_size:
        raise ValueError("cell_size conflicts with MappingPlan")
    view = planned_model(model, mapping_plan)
    text, manifest = _serialize_planned_model(view, mapping_plan.cell_size)
    return SerializationResult(
        text, manifest,
        {e.entity_key: list(e.fds_primitive_ids) for e in view.elements},
        view.exported_bounds, view.simulation_domain,
    )


def _serialize_planned_model(model, cell_size):
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
    representation_bounds = [e.representation_bounds or e.bounding_box for e in active]
    bounds = bounds_for_vertices([v for b in representation_bounds if b for v in (
        [b.xmin, b.ymin, b.zmin], [b.xmax, b.ymax, b.zmax],
    )])
    model.exported_bounds = bounds
    if model.simulation_domain:
        ijk, mesh_xb = compute_mesh_grid(model.simulation_domain, cell_size=cell_size)
        lines.append(
            f"&MESH IJK={ijk[0]},{ijk[1]},{ijk[2]}, XB={format_xb(mesh_xb)} /"
        )
    else:
        lines.append("! INCOMPLETE: simulation domain has not been declared")
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
        if strategy in (MappingStrategy.NONE, MappingStrategy.EXCLUDED_SCOPE):
            continue
        if strategy in (MappingStrategy.GEOM, MappingStrategy.OBST) and (
            not elem.mesh or not valid_solid(elem.mesh)
        ):
            raise ValueError(f"Invalid emitting geometry: {elem.entity_key}")
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
                f"&OBST ID='{prim_id}', XB={format_xb((elem.representation_bounds or elem.bounding_box).to_xb())}, SURF_ID='CONCRETE' /"
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
                ",".join(format(x, ".17g") for x in v) for v in elem.mesh.vertices
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
