"""Structured FDS MESH serialization for Local MeshPlan."""

from __future__ import annotations

from ifc_to_fds.validation.parser import parse_fds

from .mesh_plan_models import ResolvedLocalMeshPlan


def _format_values(values: list[float]) -> str:
    return ",".join(
        str(int(value))
        if float(value).is_integer()
        else format(float(value), ".17g")
        for value in values
    )


def apply_local_mesh_plan(base_text: str, plan: ResolvedLocalMeshPlan) -> str:
    """Replace base MESH records by parser source spans, never by regex."""

    parsed = parse_fds(base_text)
    if parsed.errors or parsed.unsupported:
        raise ValueError("Cannot replace MESH records in invalid verified base")
    records = [record for record in parsed.records if record.kind == "MESH"]
    if not records or any(record.text_span is None for record in records):
        raise ValueError("Verified base MESH records have no source spans")

    rendered = "\n".join(
        (
            f"&MESH ID='{mesh.id}', "
            f"IJK={mesh.ijk[0]},{mesh.ijk[1]},{mesh.ijk[2]}, "
            f"XB={_format_values(mesh.bounds.to_xb())} /"
        )
        for mesh in plan.meshes
    )

    spans = sorted(record.text_span for record in records if record.text_span)
    chunks: list[str] = []
    cursor = 0
    for index, (start, stop) in enumerate(spans):
        chunks.append(base_text[cursor:start])
        if index == 0:
            chunks.append(rendered)
        cursor = stop
    chunks.append(base_text[cursor:])
    result = "".join(chunks)

    checked = parse_fds(result)
    if checked.errors or checked.unsupported:
        raise ValueError(
            f"Resolved LocalMeshPlan produced invalid FDS: "
            f"{checked.errors + checked.unsupported}"
        )
    emitted = [record for record in checked.records if record.kind == "MESH"]
    if [record.id for record in emitted] != [mesh.id for mesh in plan.meshes]:
        raise ValueError(
            "Resolved LocalMeshPlan MESH identity differs after serialization"
        )
    return result
