"""IFC opening review queue: không suy diễn trạng thái cửa hoặc đường khói.

Đầu ra có IFC GlobalId/STEP ID để kỹ sư tìm phần tử trong công trình.
PHẢI lưu riêng tư, không gắn vào public CI artifact hoặc GitHub issues.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import ifcopenshell

from .inventory import compute_file_sha256
from .source_dossier import write_source_dossier


def _step_id(value: Any) -> int | None:
    if value is None:
        return None
    result = value.id()
    if not isinstance(result, int) or result <= 0:
        return None
    return result


def _entity_type(value: Any) -> str | None:
    return str(value.is_a()) if value is not None else None


def _identifier(value: Any) -> dict[str, Any]:
    """Định danh phải giữ trong hồ sơ riêng tư, không ghi ra logs."""
    return {
        "step_id": _step_id(value),
        "global_id": getattr(value, "GlobalId", None) if value is not None else None,
        "ifc_type": _entity_type(value),
    }


def assemble_opening_review(
    ifc_file: Any, *, source_sha256: str
) -> dict[str, Any]:
    """Duyệt quan hệ void/fill, không sử dụng geometry engine hay thông số khí."""
    if len(source_sha256) != 64 or any(
        ch not in "0123456789abcdef" for ch in source_sha256
    ):
        raise ValueError("Invalid source hash")

    opening_objects = tuple(ifc_file.by_type("IfcOpeningElement"))
    opening_by_id = {_step_id(o): o for o in opening_objects}
    if None in opening_by_id or len(opening_by_id) != len(opening_objects):
        raise ValueError("Invalid or duplicated opening STEP ID")

    voids: dict[int, list[Any]] = defaultdict(list)
    fills: dict[int, list[Any]] = defaultdict(list)
    unlinked_voids = 0
    unlinked_fills = 0
    void_relations = tuple(ifc_file.by_type("IfcRelVoidsElement"))
    fill_relations = tuple(ifc_file.by_type("IfcRelFillsElement"))
    doors = tuple(ifc_file.by_type("IfcDoor"))
    linked_door_ids: set[int] = set()
    for rel in void_relations:
        opening_id = _step_id(getattr(rel, "RelatedOpeningElement", None))
        if opening_id not in opening_by_id:
            unlinked_voids += 1
            continue
        voids[opening_id].append(rel)
    for rel in fill_relations:
        opening_id = _step_id(getattr(rel, "RelatingOpeningElement", None))
        if opening_id not in opening_by_id:
            unlinked_fills += 1
            continue
        fills[opening_id].append(rel)
        element = getattr(rel, "RelatedBuildingElement", None)
        if element is not None and element.is_a("IfcDoor"):
            door_id = _step_id(element)
            if door_id is not None:
                linked_door_ids.add(door_id)

    queue = []
    for opening_id in sorted(opening_by_id):
        opening = opening_by_id[opening_id]
        host_entities = [
            getattr(rel, "RelatingBuildingElement", None)
            for rel in voids[opening_id]
        ]
        fill_entities = [
            getattr(rel, "RelatedBuildingElement", None)
            for rel in fills[opening_id]
        ]
        reasons: set[str] = set()
        if not voids[opening_id]:
            reasons.add("OPENING_WITHOUT_VOID_RELATION")
        if not fills[opening_id]:
            reasons.add("NO_FILLING_RELATION")
        if len(voids[opening_id]) > 1:
            reasons.add("MULTIPLE_VOID_RELATIONS")
        if len(fills[opening_id]) > 1:
            reasons.add("MULTIPLE_FILLING_RELATIONS")
        if any(host is None for host in host_entities):
            reasons.add("MISSING_VOID_HOST")
        if any(fill is None for fill in fill_entities):
            reasons.add("MISSING_FILL_ELEMENT")
        if fills[opening_id] and not voids[opening_id]:
            reasons.add("FILLING_WITHOUT_VOID_RELATION")
        if not getattr(opening, "Representation", None):
            reasons.add("OPENING_HAS_NO_REPRESENTATION")
        reasons.add("PHYSICAL_OPEN_CLOSE_STATE_NOT_PROVEN")
        reasons.add("FDS_EFFECTIVE_VOID_NOT_VERIFIED")
        queue.append({
            "opening": _identifier(opening),
            "void_relation_count": len(voids[opening_id]),
            "fill_relation_count": len(fills[opening_id]),
            "hosts": [_identifier(obj) for obj in host_entities],
            "fill_elements": [_identifier(obj) for obj in fill_entities],
            "review_reasons": sorted(reasons),
            "human_review_status": "UNREVIEWED",
            "physical_state": "UNKNOWN",
            "airflow_connectivity": "NOT_EVALUATED",
            "fds_effective_geometry": "NOT_EVALUATED",
        })

    count_with_fill = sum(bool(fills[oid]) for oid in opening_by_id)
    unlinked_doors = sorted(
        (door for door in doors if _step_id(door) not in linked_door_ids),
        key=lambda door: _step_id(door) or 0,
    )
    door_review_queue = [
        {
            "door": _identifier(door),
            "reason": "DOOR_WITHOUT_IFC_FILLING_RELATION",
            "human_review_status": "UNREVIEWED",
            "physical_state": "UNKNOWN",
        }
        for door in unlinked_doors
    ]
    return {
        "schema_version": "1.0",
        "source_sha256": source_sha256,
        "ifc_schema": str(ifc_file.schema),
        "privacy_classification": "PRIVATE_SOURCE_IDENTIFIERS",
        "opening_count": len(opening_by_id),
        "void_relation_count": len(void_relations),
        "fill_relation_count": len(fill_relations),
        "openings_with_fill_relation": count_with_fill,
        "openings_without_fill_relation": len(opening_by_id) - count_with_fill,
        "door_count": len(doors),
        "door_without_filling_relation_count": len(unlinked_doors),
        "door_review_queue": door_review_queue,
        "unlinked_void_relation_count": unlinked_voids,
        "unlinked_fill_relation_count": unlinked_fills,
        "opening_review_queue": queue,
        "source_geometry_verdict": "NOT_EVALUATED",
        "mapping_verdict": "NOT_EVALUATED",
        "airflow_verdict": "NOT_EVALUATED",
        "solver_verdict": "NOT_RUN",
        "scientific_verdict": "INCONCLUSIVE",
        "review_approval": "NOT_GRANTED",
    }


def inspect_opening_review(path: str | Path) -> dict[str, Any]:
    """Bảo đảm source SHA không thay đổi khi parse, không in dữ liệu nguồn."""
    source = Path(path)
    if not source.is_file() or source.suffix.lower() != ".ifc":
        raise ValueError("Expected private IFC file")
    try:
        before_size = source.stat().st_size
        before_sha = compute_file_sha256(str(source))
        model = ifcopenshell.open(str(source))
        result = assemble_opening_review(model, source_sha256=before_sha)
        if source.stat().st_size != before_size or compute_file_sha256(str(source)) != before_sha:
            raise ValueError("Source IFC changed during opening review")
    except (OSError, RuntimeError, TypeError) as exc:
        raise ValueError("Unable to inspect private IFC opening relations") from exc
    return result


def save_opening_review(path: str | Path, report: dict[str, Any]) -> None:
    """Tái sử dụng file mode 0600 và O_EXCL của Source Dossier A1."""
    write_source_dossier(path, report)
