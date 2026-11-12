"""Preflight tọa độ IFC: chỉ kiểm tra ObjectPlacement, không dựng BREP.

Bằng chứng có tính riêng tư: không xuất ma trận, tọa độ, GUID, STEP ID, tên
công trình, hoặc đường dẫn. Không xác nhận hình học hay tính đúng đắn FDS.
"""

from __future__ import annotations

from collections import Counter
import math
from pathlib import Path
from typing import Any

import ifcopenshell
import numpy as np

from .inventory import compute_file_sha256
from .placement import get_local_placement
from .source_dossier import write_source_dossier
from .units import get_length_unit_scale


def _coordinate_band(max_absolute_m: float) -> str:
    """Chỉ công bố dải cường độ, không công bố tọa độ công trình."""
    if max_absolute_m < 100.0:
        return "BELOW_100_M"
    if max_absolute_m < 1000.0:
        return "100_TO_1000_M"
    if max_absolute_m < 10000.0:
        return "1000_TO_10000_M"
    if max_absolute_m < 100000.0:
        return "10000_TO_100000_M"
    return "AT_LEAST_100000_M"


def _classify_local_placement(placement: Any, scale: float) -> tuple[str, float | None]:
    """Đếm chain và kiểm tra ma trận rigid; tuyệt đối không gọi OCC."""
    if placement is None:
        return "MISSING", None
    visited: set[int] = set()
    current = placement
    for _ in range(65):
        if current is None:
            break
        if not current.is_a("IfcLocalPlacement"):
            return "UNSUPPORTED", None
        step_id = current.id()
        if not isinstance(step_id, int) or step_id <= 0 or step_id in visited:
            return "CYCLE_OR_INVALID_ID", None
        visited.add(step_id)
        current = current.PlacementRelTo
    else:
        return "DEPTH_EXCEEDED", None

    try:
        matrix = np.asarray(get_local_placement(placement), dtype=float)
    except (ValueError, TypeError, RuntimeError, RecursionError, AttributeError):
        return "MATRIX_UNREADABLE", None
    if matrix.shape != (4, 4) or not bool(np.isfinite(matrix).all()):
        return "NONFINITE_OR_BAD_SHAPE", None
    if not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], rtol=0.0, atol=1e-10):
        return "NON_RIGID", None

    rotation = matrix[:3, :3]
    determinant = float(np.linalg.det(rotation))
    if (
        not math.isfinite(determinant)
        or abs(determinant - 1.0) > 1e-6
        or not np.allclose(
            rotation.T @ rotation, np.eye(3), rtol=0.0, atol=1e-6
        )
    ):
        return "NON_RIGID", None
    # Chỉ đổi phần tịnh tiến từ đơn vị IFC sang mét.
    with np.errstate(over="ignore"):
        abs_translation = np.abs(matrix[:3, 3] * scale)
    if not bool(np.isfinite(abs_translation).all()):
        return "NONFINITE_TRANSLATION_M", None
    return "READABLE_RIGID", float(np.max(abs_translation))


def summarize_coordinate_placements(
    ifc_file: Any,
    *,
    source_sha256: str,
    length_unit: str,
    scale_to_meters: float,
    max_products: int = 25000,
) -> dict[str, Any]:
    """Kiểm tra placement các IfcProduct, hạn mức để tránh nghẽn IFC lớn.

    Không xử lý coordinates bên trong SweptSolid/FacetedBrep/IfcMappedItem,
    hay IfcGeometricRepresentationContext.WorldCoordinateSystem.
    """
    if (
        len(source_sha256) != 64
        or any(c not in "0123456789abcdef" for c in source_sha256)
        or not math.isfinite(scale_to_meters)
        or scale_to_meters <= 0.0
    ):
        raise ValueError("Invalid source hash or IFC length scale")
    if isinstance(max_products, bool) or not isinstance(max_products, int) or max_products <= 0:
        raise ValueError("max_products must be a positive integer")

    products = ifc_file.by_type("IfcProduct")
    product_count = len(products)
    # Lấy mẫu theo IFC STEP order ổn định; không ghi các ID ra report.
    selected = sorted(products, key=lambda entity: entity.id())[:max_products]
    counts: Counter[str] = Counter()
    max_abs = 0.0
    for product in selected:
        status, magnitude = _classify_local_placement(
            getattr(product, "ObjectPlacement", None), scale_to_meters
        )
        counts[status] += 1
        if magnitude is not None:
            max_abs = max(max_abs, magnitude)

    warnings = [
        "REPRESENTATION_COORDINATES_NOT_EVALUATED",
        "GEOMETRY_KERNEL_NOT_RUN",
        "WORLD_TO_LOCAL_REBASE_NOT_EXECUTED",
    ]
    if product_count > max_products:
        warnings.append("PLACEMENT_SCAN_INCOMPLETE")
    if counts["MISSING"]:
        warnings.append("PRODUCT_PLACEMENT_MISSING")
    if any(counts[key] for key in (
        "UNSUPPORTED", "CYCLE_OR_INVALID_ID", "DEPTH_EXCEEDED",
        "MATRIX_UNREADABLE", "NONFINITE_OR_BAD_SHAPE", "NON_RIGID",
        "NONFINITE_TRANSLATION_M",
    )):
        warnings.append("PRODUCT_PLACEMENT_INVALID_OR_UNSUPPORTED")
    if max_abs >= 1000.0:
        warnings.append("LARGE_COORDINATE_MAGNITUDE_REQUIRES_REVIEW")
    return {
        "schema_version": "1.0",
        "source_sha256": source_sha256,
        "ifc_schema": str(ifc_file.schema),
        "length_unit": str(length_unit),
        "unit_scale_to_meters": scale_to_meters,
        "total_products": product_count,
        "examined_products": len(selected),
        "placement_status_counts": dict(sorted(counts.items())),
        "maximum_absolute_translation_band_m": _coordinate_band(max_abs),
        "warnings": sorted(warnings),
        "placement_verdict": "REVIEW_REQUIRED",
        "geometry_verdict": "NOT_EVALUATED",
        "mapping_verdict": "NOT_EVALUATED",
        "solver_verdict": "NOT_RUN",
        "scientific_verdict": "INCONCLUSIVE",
        "approval_status": "DRAFT",
    }


def inspect_coordinate_file(
    file_path: str | Path, *, max_products: int = 25000
) -> dict[str, Any]:
    """Kiểm tra identity trước/sau khi đọc IFC; không đưa file path vào error."""
    path = Path(file_path)
    if not path.is_file() or path.suffix.lower() != ".ifc":
        raise ValueError("Expected a private IFC file")
    try:
        size_before = path.stat().st_size
        sha_before = compute_file_sha256(str(path))
        ifc_file = ifcopenshell.open(str(path))
        unit, scale = get_length_unit_scale(ifc_file)
        result = summarize_coordinate_placements(
            ifc_file,
            source_sha256=sha_before,
            length_unit=unit,
            scale_to_meters=scale,
            max_products=max_products,
        )
        if (
            size_before != path.stat().st_size
            or sha_before != compute_file_sha256(str(path))
        ):
            raise ValueError("Source IFC changed while inspecting placements")
    except (OSError, RuntimeError, TypeError) as exc:
        raise ValueError("Cannot inspect IFC coordinate placements") from exc
    return result


def save_coordinate_preflight(
    path: str | Path, report: dict[str, Any]
) -> None:
    """Dùng chung cơ chế file 0600/O_EXCL của Source Dossier A1."""
    write_source_dossier(path, report)
