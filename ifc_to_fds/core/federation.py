from typing import Optional, Sequence, Tuple
import math
from time import perf_counter

import numpy as np
from .inventory import extract_inventory
from .canonical import MEPGraph, CanonicalModel
from .georeferencing import declared_map_frame, require_matching_map_frames
from .placement import federate_placement, is_rigid_transform
from ifc_to_fds.geometry.mesh import bounds_for_vertices
from ifc_to_fds.mep.mep_graph import extract_mep_graph


def _translate_matrix_4x4(mat, dx: float, dy: float, dz: float):
    if mat is None:
        return None
    is_numpy = isinstance(mat, np.ndarray)
    arr = np.asarray(mat, dtype=float).reshape(4, 4)
    T = np.eye(4, dtype=float)
    T[0, 3] = -dx
    T[1, 3] = -dy
    T[2, 3] = -dz
    new_arr = T @ arr
    if is_numpy:
        if mat.ndim == 1:
            return new_arr.ravel()
        return new_arr
    elif isinstance(mat, list):
        if len(mat) == 4 and isinstance(mat[0], (list, tuple)):
            return new_arr.tolist()
        return new_arr.ravel().tolist()
    return new_arr.ravel().tolist()


def load_sources(paths, source_options=None, reference=False):
    options = source_options or {}
    if (
        len(paths) > 1
        and not options.get("common_coordinates")
        and not options.get("transforms")
    ):
        raise ValueError(
            "Multiple IFC sources require common_coordinates confirmation or explicit transforms"
        )
    models = []
    hashes = set()
    transforms = options.get("transforms", {})
    common_map_frame = None
    for index, path in enumerate(paths):
        started = perf_counter()
        model, file = extract_inventory(str(path))
        parsed = perf_counter()
        if model.source.source_id in hashes:
            raise ValueError("Duplicate source file content")
        hashes.add(model.source.source_id)
        value = transforms.get(model.source.source_id, transforms.get(str(index)))
        if len(paths) > 1 and value is None:
            if not options.get("common_coordinates"):
                raise ValueError(f"Missing transform for source {index}")
            frame = declared_map_frame(file, model.source.unit_scale_to_meters)
            require_matching_map_frames(common_map_frame, frame)
            if frame is not None:
                common_map_frame = frame
        model = extract_mep_graph(model, file)
        mep_done = perf_counter()
        if reference:
            from ifc_to_fds.geometry.engine import process_reference_geometry

            # Source was reopened above; no converter model, repairs, or geometry
            # cache is passed into this independent reader.
            process_reference_geometry(model, file)
        else:
            from ifc_to_fds.geometry.cache import cached_geometry

            model = cached_geometry(model, file)
        model.timings = dict(
            parse_s=parsed - started,
            mep_s=mep_done - parsed,
            geometry_s=perf_counter() - mep_done,
        )
        matrix = np.asarray(
            value if value is not None else np.eye(4), dtype=float
        ).reshape(4, 4)
        if not is_rigid_transform(matrix):
            raise ValueError(
                "Source transform must be a finite rigid transform, without reflection or scale"
            )
        model.source.world_transform = matrix.ravel().tolist()
        for e in model.elements:
            federate_placement(e, matrix)
            for opening in e.openings:
                if opening.placement.get("status") == "CONFIRMED":
                    local = np.asarray(opening.placement["ifc_local_to_model"]).reshape(
                        4, 4
                    )
                    opening.placement["model_to_common_world"] = matrix.ravel().tolist()
                    opening.placement["effective_world"] = (
                        (matrix @ local).ravel().tolist()
                    )
        if not np.array_equal(matrix, np.eye(4)):
            for e in model.elements:
                for mesh in [e.mesh, *[o.mesh for o in e.openings]]:
                    if mesh and len(mesh.vertices) > 0:
                        v = np.asarray(mesh.vertices)
                        mesh.vertices = (v @ matrix[:3, :3].T + matrix[:3, 3]).tolist()
                e.bounding_box = (
                    bounds_for_vertices(e.mesh.vertices) if e.mesh else None
                )
                if e.representation_bounds is not None:
                    rb = e.representation_bounds
                    corners = [
                        [x, y, z]
                        for x in (rb.xmin, rb.xmax)
                        for y in (rb.ymin, rb.ymax)
                        for z in (rb.zmin, rb.zmax)
                    ]
                    transformed_corners = (
                        np.asarray(corners) @ matrix[:3, :3].T + matrix[:3, 3]
                    ).tolist()
                    e.representation_bounds = bounds_for_vertices(transformed_corners)
                for o in e.openings:
                    o.bounding_box = (
                        bounds_for_vertices(o.mesh.vertices) if o.mesh else None
                    )
                for port in e.ports:
                    if port.world_position is not None:
                        port.world_position = (
                            matrix[:3, :3] @ port.world_position + matrix[:3, 3]
                        ).tolist()
            # Arbitrarily rotated floor planes cannot be represented by a Z interval.
            for storey in model.storey_references:
                if math.hypot(*matrix[2, :2]) > 1e-8:
                    storey.elevation_m = None
                elif storey.elevation_m is not None:
                    storey.elevation_m += matrix[2, 3]
        models.append(model)
    if not models:
        raise ValueError("At least one source IFC is required")
    totals = {
        key: sum(m.timings.get(key, 0) for m in models)
        for key in ("parse_s", "mep_s", "geometry_s")
    }
    result = models[0]
    result.timings = totals
    result.sources = [m.source for m in models]
    if len(models) > 1:
        result.elements = [e for m in models for e in m.elements]
        result.storeys = [s for m in models for s in m.storeys]
        result.storey_references = [s for m in models for s in m.storey_references]
        graph = MEPGraph()
        graph.systems = [s for m in models for s in m.mep_graph.systems]
        graph.connections = [c for m in models for c in m.mep_graph.connections]
        graph.issues = [x for m in models for x in m.mep_graph.issues]
        graph.isolated_element_ids = [
            x for m in models for x in m.mep_graph.isolated_element_ids
        ]
        graph.coverage = {m.source.source_id: m.mep_graph.coverage for m in models}
        result.mep_graph = graph
    result.model_bounds = bounds_for_vertices(
        [
            v
            for e in result.elements
            if e.bounding_box
            for v in (
                [e.bounding_box.xmin, e.bounding_box.ymin, e.bounding_box.zmin],
                [e.bounding_box.xmax, e.bounding_box.ymax, e.bounding_box.zmax],
            )
        ]
    )

    rebase_vec = options.get("rebase_vector")
    auto_rebase = options.get("auto_rebase_origin", True) or bool(options.get("rebase_origin", False))
    result, _ = rebase_model_to_origin(result, rebase_vector=rebase_vec, auto_rebase=auto_rebase)
    return result


def rebase_model_to_origin(
    model: CanonicalModel,
    rebase_vector: Optional[Sequence[float]] = None,
    auto_rebase: bool = True,
) -> Tuple[CanonicalModel, Tuple[float, float, float]]:
    rebase_vec = rebase_vector
    if rebase_vec is None and auto_rebase and model.model_bounds:
        xmin, xmax, ymin, ymax, zmin, zmax = model.model_bounds.to_xb()
        far_xy = max(abs(xmin), abs(xmax), abs(ymin), abs(ymax)) > 1000.0
        far_z = max(abs(zmin), abs(zmax)) > 1000.0
        rebase_vec = [
            float(math.floor(xmin)) if far_xy else 0.0,
            float(math.floor(ymin)) if far_xy else 0.0,
            float(math.floor(zmin)) if far_z else 0.0,
        ]

    if rebase_vec is not None:
        if (
            not isinstance(rebase_vec, (list, tuple))
            or len(rebase_vec) != 3
            or any(
                isinstance(x, bool)
                or not isinstance(x, (int, float))
                or not math.isfinite(x)
                for x in rebase_vec
            )
        ):
            raise ValueError("rebase_vector must be [x,y,z] finite numbers")
        rebase_vec = list(map(float, rebase_vec))
    else:
        rebase_vec = [0.0, 0.0, 0.0]

    if rebase_vec and any(abs(x) > 1e-6 for x in rebase_vec):
        dx, dy, dz = rebase_vec
        for e in model.elements:
            if e.mesh and e.mesh.vertices:
                e.mesh.vertices = [[v[0] - dx, v[1] - dy, v[2] - dz] for v in e.mesh.vertices]
            if e.bounding_box:
                e.bounding_box = e.bounding_box.translated(-dx, -dy, -dz)
            if e.representation_bounds:
                e.representation_bounds = e.representation_bounds.translated(-dx, -dy, -dz)

            # Update placement provenance
            if hasattr(e, "placement") and isinstance(e.placement, dict):
                if e.placement.get("effective_world") is not None:
                    e.placement["effective_world"] = _translate_matrix_4x4(
                        e.placement["effective_world"], dx, dy, dz
                    )
                if e.placement.get("model_to_common_world") is not None:
                    e.placement["model_to_common_world"] = _translate_matrix_4x4(
                        e.placement["model_to_common_world"], dx, dy, dz
                    )
            if hasattr(e, "transform") and e.transform is not None:
                e.transform = _translate_matrix_4x4(e.transform, dx, dy, dz)

            for o in e.openings:
                if o.mesh and o.mesh.vertices:
                    o.mesh.vertices = [[v[0] - dx, v[1] - dy, v[2] - dz] for v in o.mesh.vertices]
                if o.bounding_box:
                    o.bounding_box = o.bounding_box.translated(-dx, -dy, -dz)
                if hasattr(o, "placement") and isinstance(o.placement, dict):
                    if o.placement.get("effective_world") is not None:
                        o.placement["effective_world"] = _translate_matrix_4x4(
                            o.placement["effective_world"], dx, dy, dz
                        )
                    if o.placement.get("model_to_common_world") is not None:
                        o.placement["model_to_common_world"] = _translate_matrix_4x4(
                            o.placement["model_to_common_world"], dx, dy, dz
                        )

            for port in e.ports:
                if port.world_position:
                    port.world_position = [
                        port.world_position[0] - dx,
                        port.world_position[1] - dy,
                        port.world_position[2] - dz,
                    ]
        for storey in model.storey_references:
            if storey.elevation_m is not None:
                storey.elevation_m -= dz
        for field in ("model_bounds", "simulation_domain", "exported_bounds"):
            bounds = getattr(model, field)
            if bounds is not None:
                setattr(model, field, bounds.translated(-dx, -dy, -dz))

        total_rebase = [a + b for a, b in zip(model.source.rebase_vector, rebase_vec)]
        model.source.rebase_vector = total_rebase
        for source in model.sources:
            source.rebase_vector = total_rebase.copy()

        return model, (dx, dy, dz)

    return model, (0.0, 0.0, 0.0)

