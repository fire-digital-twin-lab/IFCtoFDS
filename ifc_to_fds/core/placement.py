"""Placement provenance; matrices act on metre-valued column vectors."""

import numpy as np
from ifcopenshell.util.placement import get_cartesiantransformationoperator3d


def is_rigid_transform(matrix, *, atol=1e-8):
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        return False
    rotation = matrix[:3, :3]
    return (
        np.allclose(matrix[3], [0, 0, 0, 1], atol=atol, rtol=0)
        and np.allclose(rotation.T @ rotation, np.eye(3), atol=atol, rtol=0)
        and abs(np.linalg.det(rotation) - 1.0) <= atol
    )


def _unit_direction(values, size):
    vector = np.asarray(values, dtype=float)
    if vector.shape != (size,) or not np.isfinite(vector).all():
        raise ValueError("Invalid IFC direction ratios")
    # Giữ cùng kết quả binary64 cho hướng thông thường và tránh tràn
    # hoặc hụt dưới khi tỷ lệ hướng nằm ngoài miền tính norm trực tiếp.
    with np.errstate(over="ignore", under="ignore"):
        length = np.linalg.norm(vector)
    if np.isfinite(length) and length >= np.sqrt(np.finfo(float).tiny):
        return vector / length
    scale = np.max(np.abs(vector))
    if scale == 0:
        raise ValueError("IFC direction must be nonzero")
    vector = vector / scale
    return vector / np.linalg.norm(vector)


def axis_placement_matrix(placement):
    if placement.is_a("IfcAxis2Placement2D"):
        dimension = 2
        ref = placement.RefDirection
        x = _unit_direction(ref.DirectionRatios if ref else (1, 0), dimension)
        rotation = np.array([[x[0], -x[1]], [x[1], x[0]]])
    elif placement.is_a("IfcAxis2Placement3D"):
        dimension = 3
        axis, ref = placement.Axis, placement.RefDirection
        z = _unit_direction(axis.DirectionRatios if axis else (0, 0, 1), dimension)
        if ref is None and np.any(z[:2] != 0):
            # OCC có thể chọn trục X khác phép chiếu mặc định của IFC.
            raise ValueError("Tilted IFC Axis requires RefDirection to confirm geometry provenance")
        reference = _unit_direction(ref.DirectionRatios if ref else (1, 0, 0), dimension)
        # Dạng trực chuẩn Gram–Schmidt dùng tích có hướng, tránh trừ hai vector gần nhau.
        y = np.cross(z, reference)
        length = np.linalg.norm(y)
        if length <= 16 * np.finfo(float).eps:
            raise ValueError("IFC Axis and RefDirection are parallel or numerically unresolved")
        y /= length
        # Nếu hai hướng đã vuông góc, phép chiếu bảo toàn hướng tham chiếu.
        x = reference if np.dot(z, reference) == 0 else np.cross(y, z)
        rotation = np.column_stack((x, y, z))
    else:
        raise ValueError(f"Unsupported IFC axis placement: {placement.is_a()}")

    origin = np.asarray(placement.Location.Coordinates, dtype=float)
    if origin.shape != (dimension,) or not np.isfinite(origin).all():
        raise ValueError("Invalid IFC placement origin")
    matrix = np.eye(4)
    matrix[:dimension, :dimension] = rotation
    matrix[:dimension, 3] = origin
    return matrix


def _placement_chain(placement):
    chain = []
    seen = set()
    while placement is not None:
        if not placement.is_a("IfcLocalPlacement") or placement.id() in seen:
            raise ValueError("Cyclic or unsupported IFC placement")
        seen.add(placement.id())
        chain.append(placement)
        placement = placement.PlacementRelTo
    return chain


def _compose_placements(chain):
    matrix = np.eye(4)
    for placement in reversed(chain):
        matrix = matrix @ axis_placement_matrix(placement.RelativePlacement)
    if not is_rigid_transform(matrix):
        raise ValueError("Nonrigid or nonfinite IFC placement")
    return matrix


def get_local_placement(placement):
    """Đọc chuỗi IfcLocalPlacement, giữ độ tịnh tiến ở đơn vị của IFC."""
    return _compose_placements(_placement_chain(placement))


def _mapped_item_transform(item):
    target = item.MappingTarget
    if not target.is_a("IfcCartesianTransformationOperator3D"):
        raise ValueError("Only 3D mapped item transforms have confirmed provenance")
    for field in ("Scale", "Scale2", "Scale3"):
        scale = getattr(target, field, None)
        if scale is not None and (not np.isfinite(scale) or scale <= 0):
            raise ValueError("Mapped representation has invalid axis scale")
    matrix = get_cartesiantransformationoperator3d(target)
    basis = matrix[:3, :3]
    norms = np.linalg.norm(basis, axis=0)
    if not np.isfinite(norms).all() or np.any(norms <= 0):
        raise ValueError("Mapped representation has invalid axis scale")
    basis = basis / norms
    if not np.allclose(basis.T @ basis, np.eye(3), atol=1e-8, rtol=0):
        raise ValueError("Mapped representation has unresolved nonorthogonal axes")
    return matrix @ axis_placement_matrix(item.MappingSource.MappingOrigin)


def extract_placement(product, scale):
    value = dict(
        status="UNVERIFIED",
        units="METRE",
        matrix_order="ROW_MAJOR",
        vector_convention="COLUMN",
        source_unit_scale=scale,
        chain=[],
        mapped_items=[],
    )
    placement = getattr(product, "ObjectPlacement", None)
    if placement is None:
        value.update(status="MISSING", reason="IFC product has no ObjectPlacement")
        return value
    try:
        chain = _placement_chain(placement)
        value["chain"] = [item.id() for item in chain]
        matrix = _compose_placements(chain)
        matrix[:3, 3] *= scale
        if not np.isfinite(matrix).all():
            raise ValueError("Nonfinite IFC placement")
        value.update(
            status="CONFIRMED",
            ifc_local_to_model=matrix.ravel().tolist(),
            model_to_common_world=np.eye(4).ravel().tolist(),
            effective_world=matrix.ravel().tolist(),
        )
        visited = set()

        def walk(items, parent=None):
            for item in items:
                if not item.is_a("IfcMappedItem"):
                    continue
                if item.id() in visited:
                    raise ValueError(
                        "Cyclic/repeated mapped representation requires review"
                    )
                visited.add(item.id())
                mapped = _mapped_item_transform(item)
                mapped[:3, 3] *= scale
                if not np.isfinite(mapped).all():
                    raise ValueError("Nonfinite mapped representation")
                value["mapped_items"].append(
                    dict(
                        step_id=item.id(),
                        parent_step_id=parent,
                        mapping_source_step_id=item.MappingSource.id(),
                        matrix=mapped.ravel().tolist(),
                    )
                )
                walk(item.MappingSource.MappedRepresentation.Items, item.id())
                visited.remove(item.id())

        for representation in getattr(
            getattr(product, "Representation", None), "Representations", []
        ):
            walk(representation.Items)
    except Exception as exc:
        value.update(status="UNVERIFIED", reason=str(exc))
    return value


def federate_placement(element, matrix):
    if element.placement.get("status") == "CONFIRMED":
        local = np.asarray(element.placement["ifc_local_to_model"]).reshape(4, 4)
        element.placement["model_to_common_world"] = matrix.ravel().tolist()
        element.transform = (matrix @ local).ravel().tolist()
        element.placement["effective_world"] = element.transform
