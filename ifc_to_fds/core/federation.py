"""Explicit source federation; no alignment by bounding boxes or GlobalId."""

import numpy as np
from time import perf_counter
from .inventory import extract_inventory
from .canonical import MEPGraph
from ifc_to_fds.geometry.mesh import bounds_for_vertices
from ifc_to_fds.mep.mep_graph import extract_mep_graph


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
            # Independent audit uses per-product create_shape rather than converter iterator/cache.
            from ifc_to_fds.geometry.engine import (
                create_geom_settings,
                extract_element_geometry,
            )
            from .canonical import CanonicalElement, GeometryStatus
            from ifc_to_fds.geometry.mesh import valid_solid

            settings = create_geom_settings()
            for e in model.elements:
                if e.has_3d_geometry:
                    e.mesh = extract_element_geometry(file, e, settings)
                    e.bounding_box = (
                        bounds_for_vertices(e.mesh.vertices) if e.mesh else None
                    )
                    e.geometry_status = (
                        GeometryStatus.VALID
                        if e.mesh and valid_solid(e.mesh)
                        else GeometryStatus.FAILED
                    )
                    for o in e.openings:
                        o.mesh = extract_element_geometry(
                            file,
                            CanonicalElement(
                                global_id=o.opening_global_id,
                                step_id=o.opening_step_id,
                                ifc_type="IfcOpeningElement",
                            ),
                            settings,
                        )
                        o.bounding_box = (
                            bounds_for_vertices(o.mesh.vertices) if o.mesh else None
                        )
        else:
            from ifc_to_fds.geometry.cache import cached_geometry

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
        from .placement import federate_placement

        for e in model.elements:
            federate_placement(e, matrix)
        if not np.allclose(matrix, np.eye(4)):
            for e in model.elements:
                for mesh in [e.mesh, *[o.mesh for o in e.openings]]:
                    if mesh:
                        v = np.asarray(mesh.vertices)
                        mesh.vertices = (v @ matrix[:3, :3].T + matrix[:3, 3]).tolist()
                e.bounding_box = (
                    bounds_for_vertices(e.mesh.vertices) if e.mesh else None
                )
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
        [v for e in result.elements if e.mesh for v in e.mesh.vertices]
    )
    return result
