"""Scope selection retains whole intersecting solids; never clips geometry."""

from ifc_to_fds.core.canonical import BoundingBox, ScopeDecision
from ifc_to_fds.domain.scope import (
    SelectionScope as SelectionScope,
    SpatialScope as SpatialScope,
)
from ifc_to_fds.geometry.mesh import intersects_box, bounds_for_vertices
from ifc_to_fds.diagnostics import operation


@operation("SCOPE")
def apply_spatial_scope(model, scope):
    building_bounds = {}
    for e in model.elements:
        if e.mesh and e.building_id and e.role == "PHYSICAL":
            bounds = bounds_for_vertices(e.mesh.vertices)
            if bounds:
                building_bounds.setdefault((e.source_id, e.building_id), []).extend(
                    [
                        [bounds.xmin, bounds.ymin, bounds.zmin],
                        [bounds.xmax, bounds.ymax, bounds.zmax],
                    ]
                )
    building_bounds = {
        key: bounds_for_vertices(points) for key, points in building_bounds.items()
    }
    selected = []
    for selector in scope.storeys:
        hits = [s for s in model.storey_references if selector in (s.name, s.storey_id)]
        if len(hits) != 1:
            raise ValueError(
                f"Storey {selector!r} is unknown or ambiguous; use source-qualified storey_id"
            )
        selected.extend(hits)
    intervals = []
    for s in selected:
        elevations = sorted(
            x.elevation_m
            for x in model.storey_references
            if x.source_id == s.source_id
            and x.building_id == s.building_id
            and x.elevation_m is not None
        )
        upper = next(
            (
                x
                for x in elevations
                if s.elevation_m is not None and x > s.elevation_m + 1e-6
            ),
            None,
        )
        if upper is None:
            # Top storey: derive the upper limit only from this source/building,
            # or an explicitly requested scope bound. Never invent a floor height.
            if scope.bounding_box:
                upper = scope.bounding_box.zmax
            else:
                bounds = [
                    bounds_for_vertices(e.mesh.vertices)
                    for e in model.elements
                    if e.mesh
                    and e.role == "PHYSICAL"
                    and e.source_id == s.source_id
                    and e.building_id == s.building_id
                ]
                upper = max((b.zmax for b in bounds if b), default=None)
        if s.elevation_m is not None and upper is not None and upper > s.elevation_m:
            intervals.append((s, s.elevation_m, upper))
    selected_ids = {s.storey_id for s in selected}
    model.requested_scope = scope.model_dump(mode="json")
    for e in model.elements:
        e.scope_decision = ScopeDecision.IN_SCOPE
        e.scope_rationale = "Full model"
        if not selected and not scope.bounding_box:
            continue
        direct = not selected or e.storey_id in selected_ids
        regions = []
        if scope.bounding_box:
            regions = [scope.bounding_box]
        elif model.model_bounds:
            regions = [model.model_bounds]
        if selected and regions:
            clipped = []
            for region in regions:
                for owner, low, high in intervals:
                    if (
                        e.building_id is not None and e.building_id != owner.building_id
                    ) or e.source_id != owner.source_id:
                        continue
                    building = building_bounds.get((owner.source_id, owner.building_id))
                    candidate = region
                    if building:
                        candidate = (
                            BoundingBox(
                                xmin=max(region.xmin, building.xmin),
                                xmax=min(region.xmax, building.xmax),
                                ymin=max(region.ymin, building.ymin),
                                ymax=min(region.ymax, building.ymax),
                                zmin=region.zmin,
                                zmax=region.zmax,
                            )
                            if min(region.xmax, building.xmax)
                            > max(region.xmin, building.xmin)
                            and min(region.ymax, building.ymax)
                            > max(region.ymin, building.ymin)
                            else None
                        )
                    if candidate is None:
                        continue
                    zlo, zhi = max(candidate.zmin, low), min(candidate.zmax, high)
                    if zhi > zlo:
                        clipped.append(
                            candidate.model_copy(update={"zmin": zlo, "zmax": zhi})
                        )
            regions = clipped
        hit = False
        uncertain = False
        if e.mesh and e.bounding_box:
            for region in regions:
                if e.bounding_box.intersects(region):
                    try:
                        hit = hit or intersects_box(e.mesh, region)
                    except Exception:
                        uncertain = True
        elif e.has_3d_geometry and e.role == "PHYSICAL":
            if regions:
                uncertain = True
        if (
            selected
            and not intervals
            and not scope.bounding_box
            and not direct
            and e.role == "PHYSICAL"
        ):
            uncertain = True
        if direct and not scope.bounding_box:
            e.scope_rationale = "Assigned to selected storey"
        elif hit and (direct or scope.include_connecting_structures):
            e.scope_decision = ScopeDecision.BOUNDARY_RETAINED
            e.scope_rationale = (
                "Whole element intersects selected volume; boundary retained"
            )
        elif uncertain:
            e.scope_decision = ScopeDecision.UNRESOLVED
            e.scope_rationale = "Cannot prove scope intersection; provide bounds or repair source geometry"
        else:
            e.scope_decision = ScopeDecision.OUT_OF_SCOPE
            e.scope_rationale = "Outside selected storeys and spatial volume"
    included = [
        e
        for e in model.elements
        if e.role == "PHYSICAL"
        and e.scope_decision
        in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
        and e.mesh
    ]
    if not included:
        raise ValueError("Selected scope contains no physical geometry")
    return model
