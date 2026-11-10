"""Preflight quan hệ IfcSpace/IfcRelSpaceBoundary; không suy luận đường khói.

Báo cáo chứa GUID/STEP ID và chỉ lưu cục bộ có phân quyền. IFC2X3 không
có boundary không đồng nghĩa không có khoang, tường, hoặc đường khí động.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import ifcopenshell

from .inventory import compute_file_sha256
from .source_dossier import write_source_dossier


def _id(entity: Any) -> int | None:
    if entity is None:
        return None
    value = entity.id()
    return value if isinstance(value, int) and value > 0 else None


def _type(entity: Any) -> str | None:
    return str(entity.is_a()) if entity is not None else None


def _reference(entity: Any) -> dict[str, Any]:
    return {
        "step_id": _id(entity),
        "global_id": getattr(entity, "GlobalId", None) if entity is not None else None,
        "ifc_type": _type(entity),
    }


def _enum(value: Any) -> str:
    """Không bịa enum khi IFC thiếu giá trị."""
    return str(value) if value is not None else "UNSPECIFIED"


def assemble_spatial_boundary_review(
    ifc_file: Any, *, source_sha256: str
) -> dict[str, Any]:
    """Ghi bằng chứng quan hệ trong IFC, tuyệt đối không suy ra adjacency."""
    if len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("Invalid source hash")

    spaces = tuple(ifc_file.by_type("IfcSpace"))
    known_spaces: dict[int, Any] = {}
    for space in spaces:
        key = _id(space)
        if key is None or key in known_spaces:
            raise ValueError("Invalid or duplicated IfcSpace STEP ID")
        known_spaces[key] = space

    # by_type(IfcRelSpaceBoundary) bao gồm subtype 1st/2nd level trong IFC4.
    boundaries = tuple(ifc_file.by_type("IfcRelSpaceBoundary"))
    per_space: dict[int, list[Any]] = defaultdict(list)
    unlinked_boundary_count = 0
    boundary_types: Counter[str] = Counter()
    related_element_types: Counter[str] = Counter()
    for relation in boundaries:
        boundary_types[_type(relation) or "UNKNOWN"] += 1
        related_element = getattr(relation, "RelatedBuildingElement", None)
        related_element_types[_type(related_element) or "MISSING"] += 1
        key = _id(getattr(relation, "RelatingSpace", None))
        if key is None or key not in known_spaces:
            unlinked_boundary_count += 1
            continue
        per_space[key].append(relation)

    queue = []
    for space_id in sorted(known_spaces):
        space = known_spaces[space_id]
        relations = sorted(per_space[space_id], key=lambda rel: _id(rel) or 0)
        reasons: set[str] = {
            "CFD_COMPARTMENT_GEOMETRY_NOT_VERIFIED",
            "AIRFLOW_CONNECTIVITY_NOT_VERIFIED",
        }
        if not relations:
            reasons.add("SPACE_WITHOUT_BOUNDARY_RELATIONS")

        boundary_records = []
        for rel in relations:
            host = getattr(rel, "RelatedBuildingElement", None)
            if host is None:
                reasons.add("BOUNDARY_WITHOUT_RELATED_BUILDING_ELEMENT")
            corresponding = getattr(rel, "CorrespondingBoundary", None)
            if corresponding is not None:
                # IFC4 CorrespondingBoundary là metadata, không phải cạnh thông khói.
                reasons.add("CORRESPONDING_BOUNDARY_REQUIRES_GEOMETRY_REVIEW")
            boundary_records.append({
                "relation": _reference(rel),
                "related_element": _reference(host),
                "physical_or_virtual": _enum(
                    getattr(rel, "PhysicalOrVirtualBoundary", None)
                ),
                "internal_or_external": _enum(
                    getattr(rel, "InternalOrExternalBoundary", None)
                ),
                "corresponding_boundary": _reference(corresponding)
                if corresponding is not None else None,
                "boundary_geometry_status": "NOT_EVALUATED",
            })
        queue.append({
            "space": _reference(space),
            "boundary_relation_count": len(relations),
            "boundaries": boundary_records,
            "review_reasons": sorted(reasons),
            "space_geometry_status": "NOT_EVALUATED",
            "airflow_connectivity": "NOT_EVALUATED",
            "human_review_status": "UNREVIEWED",
        })

    warnings: list[str] = []
    if known_spaces and not boundaries:
        warnings.append("IFC_SPACE_BOUNDARY_RELATIONS_ABSENT")
    if unlinked_boundary_count:
        warnings.append("IFC_SPACE_BOUNDARIES_UNLINKED")
    if related_element_types["MISSING"]:
        warnings.append("BOUNDARY_RELATED_ELEMENTS_MISSING")
    if not known_spaces:
        warnings.append("NO_IFC_SPACES_IN_SOURCE")
    warnings.extend([
        "BIM_SPACE_BOUNDARIES_NOT_AIRFLOW_GRAPH",
        "MEP_CONTROL_AND_OPERATION_NOT_EVALUATED",
        "FDS_EFFECTIVE_GEOMETRY_NOT_EVALUATED",
    ])

    return {
        "schema_version": "1.0",
        "source_sha256": source_sha256,
        "ifc_schema": str(ifc_file.schema),
        "privacy_classification": "PRIVATE_SOURCE_IDENTIFIERS",
        "space_count": len(known_spaces),
        "boundary_relation_count": len(boundaries),
        "boundary_class_counts": dict(sorted(boundary_types.items())),
        "related_element_class_counts": dict(sorted(related_element_types.items())),
        "boundaries_without_known_relating_space": unlinked_boundary_count,
        "space_review_queue": queue,
        "warnings": sorted(warnings),
        "spatial_adjacency_verdict": "NOT_EVALUATED",
        "airflow_verdict": "NOT_EVALUATED",
        "geometry_verdict": "NOT_EVALUATED",
        "mapping_verdict": "NOT_EVALUATED",
        "solver_verdict": "NOT_RUN",
        "scientific_verdict": "INCONCLUSIVE",
        "review_approval": "NOT_GRANTED",
    }


def inspect_spatial_boundary_review(path: str | Path) -> dict[str, Any]:
    """Bảo toàn source identity; không đưa đường dẫn công trình vào log."""
    source = Path(path)
    if not source.is_file() or source.suffix.lower() != ".ifc":
        raise ValueError("Expected private IFC file")
    try:
        before_size = source.stat().st_size
        before_sha = compute_file_sha256(str(source))
        model = ifcopenshell.open(str(source))
        report = assemble_spatial_boundary_review(model, source_sha256=before_sha)
        if source.stat().st_size != before_size or compute_file_sha256(str(source)) != before_sha:
            raise ValueError("Source IFC changed during spatial boundary review")
    except (OSError, TypeError, RuntimeError) as exc:
        raise ValueError("Unable to inspect private IFC spatial boundaries") from exc
    return report


def save_spatial_boundary_review(path: str | Path, report: dict[str, Any]) -> None:
    """Lưu riêng tư (O_EXCL; mode 0600 trên POSIX), không tự ghi đè."""
    write_source_dossier(path, report)
