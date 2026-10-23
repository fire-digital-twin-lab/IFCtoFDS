"""Explicit source federation; no alignment by bounding boxes or GlobalId."""

import numpy as np
from time import perf_counter
from ifc_to_fds.modules.bim.infrastructure.ifc.inventory import extract_inventory
from ifc_to_fds.domain.contracts import MEPGraph
from ifc_to_fds.modules.geometry.api import bounds_for_vertices
from ifc_to_fds.modules.bim.infrastructure.ifc.mep.graph_reader import extract_mep_graph


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
    for index, path in enumerate(paths):
        started = perf_counter()
        model, file = extract_inventory(str(path))
        parsed = perf_counter()
        if model.source.source_id in hashes:
            raise ValueError("Duplicate source file content")
        hashes.add(model.source.source_id)
        model = extract_mep_graph(model, file)
        mep_done = perf_counter()
        if reference:
            from ifc_to_fds.modules.geometry.api import process_reference_geometry

            # Source was reopened above; no converter model, repairs, or geometry
            # cache is passed into this independent reader.
            process_reference_geometry(model, file)
        else:
            from ifc_to_fds.modules.geometry.api import cached_geometry

            model = cached_geometry(model, file)
        model.timings = dict(
            parse_s=parsed - started,
            mep_s=mep_done - parsed,
            geometry_s=perf_counter() - mep_done,
        )
        value = transforms.get(model.source.source_id, transforms.get(str(index)))
        if len(paths) > 1 and not options.get("common_coordinates") and value is None:
            raise ValueError(f"Missing transform for source {index}")
        matrix = np.asarray(
            value if value is not None else np.eye(4), dtype=float
        ).reshape(4, 4)
        if (
            not np.isfinite(matrix).all()
            or not np.allclose(matrix[3], [0, 0, 0, 1])
            or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-8)
            or np.linalg.det(matrix[:3, :3]) < 0
        ):
            raise ValueError(
                "Source transform must be a finite rigid transform, without reflection or scale"
            )
        model.source.world_transform = matrix.ravel().tolist()
        from ifc_to_fds.modules.bim.infrastructure.ifc.placement import federate_placement

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
        if not np.allclose(matrix, np.eye(4)):
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
                if not np.allclose(matrix[2, :3], [0, 0, 1]):
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
    if rebase_vec is None and result.model_bounds:
        auto_rebase = options.get("auto_rebase_origin", True)
        if (options.get("rebase_origin") or auto_rebase) and (
            abs(result.model_bounds.xmin) > 1000.0 or abs(result.model_bounds.ymin) > 1000.0
        ):
            rebase_vec = [
                float(np.floor(result.model_bounds.xmin)),
                float(np.floor(result.model_bounds.ymin)),
                0.0,
            ]
        else:
            rebase_vec = [0.0, 0.0, 0.0]

    if rebase_vec and any(abs(x) > 1e-6 for x in rebase_vec):
        dx, dy, dz = rebase_vec
        for e in result.elements:
            if e.mesh and e.mesh.vertices:
                e.mesh.vertices = [[v[0] - dx, v[1] - dy, v[2] - dz] for v in e.mesh.vertices]
            if e.bounding_box:
                e.bounding_box.xmin -= dx
                e.bounding_box.xmax -= dx
                e.bounding_box.ymin -= dy
                e.bounding_box.ymax -= dy
                e.bounding_box.zmin -= dz
                e.bounding_box.zmax -= dz
            if e.representation_bounds:
                e.representation_bounds.xmin -= dx
                e.representation_bounds.xmax -= dx
                e.representation_bounds.ymin -= dy
                e.representation_bounds.ymax -= dy
                e.representation_bounds.zmin -= dz
                e.representation_bounds.zmax -= dz
            for o in e.openings:
                if o.mesh and o.mesh.vertices:
                    o.mesh.vertices = [[v[0] - dx, v[1] - dy, v[2] - dz] for v in o.mesh.vertices]
                if o.bounding_box:
                    o.bounding_box.xmin -= dx
                    o.bounding_box.xmax -= dx
                    o.bounding_box.ymin -= dy
                    o.bounding_box.ymax -= dy
                    o.bounding_box.zmin -= dz
                    o.bounding_box.zmax -= dz
            for port in e.ports:
                if port.world_position:
                    port.world_position = [
                        port.world_position[0] - dx,
                        port.world_position[1] - dy,
                        port.world_position[2] - dz,
                    ]
        if result.model_bounds:
            result.model_bounds.xmin -= dx
            result.model_bounds.xmax -= dx
            result.model_bounds.ymin -= dy
            result.model_bounds.ymax -= dy
            result.model_bounds.zmin -= dz
            result.model_bounds.zmax -= dz

        result.source.rebase_vector = rebase_vec
        for s in result.sources:
            s.rebase_vector = rebase_vec

    return result
