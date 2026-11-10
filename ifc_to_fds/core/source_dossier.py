"""Kiểm kê nguồn IFC không dựng hình học, không tự phê duyệt mapping.

Đầu ra an toàn để review: không chứa tên công trình, tọa độ, GUID, đường dẫn
hay bản vẽ. Không sử dụng kết quả này làm bằng chứng khoa học/geometry PASS.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import math
import os
import json
from pathlib import Path
from typing import Any

import ifcopenshell

from .units import get_length_unit_scale


_REQUIRED_TYPES = (
    "IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey",
    "IfcSpace", "IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcColumn",
    "IfcBeam", "IfcDoor", "IfcWindow", "IfcStair", "IfcStairFlight",
    "IfcRamp", "IfcRampFlight", "IfcOpeningElement", "IfcRelVoidsElement",
    "IfcRelFillsElement", "IfcRelSpaceBoundary", "IfcRelConnectsPathElements",
    "IfcRelContainedInSpatialStructure", "IfcRelAggregates", "IfcFan",
    "IfcDuctSegment", "IfcDamper", "IfcAirTerminal", "IfcDistributionPort",
    "IfcRelConnectsPorts", "IfcFacetedBrep", "IfcFace", "IfcPolyLoop",
    "IfcExtrudedAreaSolid", "IfcMappedItem",
)
_MEP_TYPES = (
    "IfcFan", "IfcDuctSegment", "IfcDamper", "IfcAirTerminal",
    "IfcDistributionPort", "IfcRelConnectsPorts",
)


def _identity(entity: Any) -> int:
    """STEP ID phục vụ phép đếm nội bộ; không xuất ra báo cáo."""
    value = entity.id()
    if not isinstance(value, int) or value <= 0:
        raise ValueError("IFC entity is missing a valid STEP identifier")
    return value


def _type(entity: Any) -> str:
    if entity is None:
        return "MISSING"
    return str(entity.is_a()).upper()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _storey_elevation(storey: Any, scale: float) -> float | None:
    """Chỉ ghi Elevation đã khai báo; KHÔNG đo vị trí 3D của hình học."""
    raw = getattr(storey, "Elevation", None)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Invalid IFC storey elevation")
    value = float(raw) * scale
    if not math.isfinite(value):
        raise ValueError("Non-finite IFC storey elevation")
    return value


def assemble_source_dossier(
    ifc_file: Any, *, sha256: str, size_bytes: int,
    length_unit: str, unit_scale_to_meters: float,
) -> dict[str, Any]:
    """Kiểm kê từng thực thể/quan hệ bằng IfcOpenShell; không gọi geometry kernel.

    Hàm này không được suy diễn tình trạng OPEN/CLOSED của các lỗ không fill,
    đường khói, hoặc khả năng vận hành HVAC từ class name của IFC.
    """
    if (
        len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256)
        or isinstance(size_bytes, bool) or size_bytes <= 0
        or not math.isfinite(unit_scale_to_meters)
        or unit_scale_to_meters <= 0
    ):
        raise ValueError("Invalid source identity or length unit")

    by_type = {kind: tuple(ifc_file.by_type(kind)) for kind in _REQUIRED_TYPES}
    counts = {kind.upper(): len(values) for kind, values in by_type.items()}

    storeys = by_type["IfcBuildingStorey"]
    storey_ids = {_identity(s) for s in storeys}
    contained: dict[int, set[int]] = defaultdict(set)
    spaces: dict[int, set[int]] = defaultdict(set)
    for rel in by_type["IfcRelContainedInSpatialStructure"]:
        structure = getattr(rel, "RelatingStructure", None)
        if structure is None or _identity(structure) not in storey_ids:
            continue
        sid = _identity(structure)
        for element in getattr(rel, "RelatedElements", ()) or ():
            eid = _identity(element)
            contained[sid].add(eid)
            if _type(element) == "IFCSPACE":
                spaces[sid].add(eid)

    for rel in by_type["IfcRelAggregates"]:
        parent = getattr(rel, "RelatingObject", None)
        if parent is None or _identity(parent) not in storey_ids:
            continue
        sid = _identity(parent)
        for element in getattr(rel, "RelatedObjects", ()) or ():
            if _type(element) == "IFCSPACE":
                spaces[sid].add(_identity(element))

    floor_records = [
        {
            "elevation_m_declared": _storey_elevation(storey, unit_scale_to_meters),
            "direct_contained_elements": len(contained[_identity(storey)]),
            "associated_spaces": len(spaces[_identity(storey)]),
        }
        for storey in storeys
    ]
    floor_records.sort(key=lambda x: (
        x["elevation_m_declared"] is None,
        x["elevation_m_declared"] if x["elevation_m_declared"] is not None else 0.0,
        x["direct_contained_elements"], x["associated_spaces"],
    ))
    for index, record in enumerate(floor_records, 1):
        record["index"] = index

    opening_ids = {_identity(o) for o in by_type["IfcOpeningElement"]}
    void_by_opening: Counter[int] = Counter()
    filled_by_opening: Counter[int] = Counter()
    hosts: Counter[str] = Counter()
    invalid_void_host = 0
    invalid_void_opening = 0
    invalid_filling = 0
    filled_doors: set[int] = set()
    fills_without_void = 0
    fill_types: Counter[str] = Counter()
    for rel in by_type["IfcRelVoidsElement"]:
        opening = getattr(rel, "RelatedOpeningElement", None)
        host = getattr(rel, "RelatingBuildingElement", None)
        if opening is None or _identity(opening) not in opening_ids:
            invalid_void_opening += 1
            continue
        void_by_opening[_identity(opening)] += 1
        if host is None:
            invalid_void_host += 1
        else:
            hosts[_type(host)] += 1

    for rel in by_type["IfcRelFillsElement"]:
        opening = getattr(rel, "RelatingOpeningElement", None)
        element = getattr(rel, "RelatedBuildingElement", None)
        if (
            opening is None or _identity(opening) not in opening_ids
            or element is None
        ):
            invalid_filling += 1
            continue
        filled_by_opening[_identity(opening)] += 1
        if _identity(opening) not in void_by_opening:
            fills_without_void += 1
        fill_types[_type(element)] += 1
        if _type(element) == "IFCDOOR":
            filled_doors.add(_identity(element))

    joined_voids = sum(
        count for opening_id, count in void_by_opening.items()
        if filled_by_opening[opening_id] > 0
    )
    unfilled_voids = sum(
        count for opening_id, count in void_by_opening.items()
        if filled_by_opening[opening_id] == 0
    )
    duplicate_void_openings = sum(count - 1 for count in void_by_opening.values() if count > 1)
    duplicate_filling_openings = sum(count - 1 for count in filled_by_opening.values() if count > 1)
    door_ids = {_identity(d) for d in by_type["IfcDoor"]}
    unreferenced_openings = len(opening_ids - set(void_by_opening))

    warnings: list[str] = []
    if unfilled_voids:
        warnings.append("UNFILLED_VOID_RELATIONS_REQUIRE_REVIEW")
    if counts["IFCRELSPACEBOUNDARY"] == 0 and counts["IFCSPACE"]:
        warnings.append("SPACE_BOUNDARY_RELATIONS_ABSENT")
    if not any(counts[k.upper()] for k in _MEP_TYPES):
        warnings.append("MEP_ENTITIES_NOT_IN_THIS_SOURCE")
    if invalid_void_host or invalid_void_opening or invalid_filling or duplicate_void_openings or duplicate_filling_openings or unreferenced_openings or fills_without_void:
        warnings.append("INVALID_OR_DUPLICATED_OPENING_RELATIONS")
    warnings.extend(("COORDINATE_PLACEMENTS_NOT_VERIFIED", "GEOMETRY_KERNEL_NOT_RUN"))
    if any(item["elevation_m_declared"] is None for item in floor_records):
        warnings.append("STOREY_ELEVATION_NOT_DECLARED")

    return {
        "schema_version": "1.0",
        "source": {
            "sha256": sha256,
            "size_bytes": size_bytes,
            "ifc_schema": str(ifc_file.schema),
            "length_unit": str(length_unit),
            "unit_scale_to_meters": unit_scale_to_meters,
        },
        "entity_counts": dict(sorted(counts.items())),
        "storeys": floor_records,
        "openings": {
            "opening_elements": len(opening_ids),
            "void_relations": len(by_type["IfcRelVoidsElement"]),
            "fill_relations": len(by_type["IfcRelFillsElement"]),
            "voids_with_filling_relation": joined_voids,
            "voids_without_filling_relation": unfilled_voids,
            "host_class_counts": dict(sorted(hosts.items())),
            "filling_class_counts": dict(sorted(fill_types.items())),
            "door_elements_without_filling_relation": len(door_ids - filled_doors),
            "invalid_void_host_relations": invalid_void_host,
            "invalid_void_opening_relations": invalid_void_opening,
            "invalid_filling_relations": invalid_filling,
            "duplicate_void_opening_relations": duplicate_void_openings,
            "duplicate_filling_opening_relations": duplicate_filling_openings,
            "opening_elements_without_void_relation": unreferenced_openings,
            "filling_relations_without_void_relation": fills_without_void,
        },
        "warnings": sorted(warnings),
        "evidence_scope": "IFC_ENTITY_RELATIONSHIP_INVENTORY_ONLY",
        "geometry_verdict": "NOT_EVALUATED",
        "mapping_verdict": "NOT_EVALUATED",
        "solver_verdict": "NOT_RUN",
        "scientific_verdict": "INCONCLUSIVE",
        "approval_status": "DRAFT",
    }


def inspect_source_dossier(path: str | Path) -> dict[str, Any]:
    """Mở nguồn một lần, không dựng geometry/mesh, không lưu IFC vào artifact."""
    source = Path(path)
    if not source.is_file() or source.suffix.lower() != ".ifc":
        raise ValueError("Expected a readable IFC file")
    # Khóa identity trước/sau parse: không gắn dossier vào file đã thay đổi.
    initial_size = source.stat().st_size
    initial_sha = _sha256(source)
    model = ifcopenshell.open(str(source))
    unit_name, scale = get_length_unit_scale(model)
    if source.stat().st_size != initial_size or _sha256(source) != initial_sha:
        raise ValueError("Source IFC changed during inventory")
    return assemble_source_dossier(
        model,
        sha256=initial_sha,
        size_bytes=initial_size,
        length_unit=unit_name,
        unit_scale_to_meters=scale,
    )


def write_source_dossier(output: str | Path, dossier: dict[str, Any]) -> None:
    """Lưu JSON không ghi đè, POSIX mode 0600 để tránh lộ IFC metadata."""
    target = Path(output)
    if target.suffix.lower() != ".json":
        raise ValueError("Dossier destination must be a JSON file")
    payload = json.dumps(dossier, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    completed = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
        completed = True
    finally:
        if not completed:
            target.unlink(missing_ok=True)
