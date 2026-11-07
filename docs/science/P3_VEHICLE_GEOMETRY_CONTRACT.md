# P3a — Vehicle identity and ground-clearance geometry contract

**Status:** implementation pending CI verification  
**Roadmap phase:** P3 — Vehicle identity & geometry  
**Scientific claim affected:** `EV-GEO-001`  
**Required evidence level for this work package:** E2 — software verification

## Problem

The legacy EV scenario represents a vehicle as one full rectangular `OBST` centered at the requested position. For the default passenger-car dimensions and a center height of 0.75 m, the lower face is at z=0 and therefore removes the underbody air gap. The legacy burner is placed on the roof plane.

That representation is retained only for backward compatibility. It is not promoted to a scientific vehicle-geometry claim.

## Root cause

The scenario request previously carried only a preset, position and optional dimensions. It had no explicit geometry mode, IFC source identity, floor reference, ground-clearance contract or battery geometry record. The emitter therefore had no information with which to fail closed.

## Contract introduced

### `LEGACY`

- default for backward compatibility;
- historical centered box remains unchanged;
- historical roof burner remains unchanged;
- no scientific clearance claim is granted.

### `PARAMETRIC`

Requires:

- explicit vehicle dimensions;
- explicit `floor_z_m`;
- explicit positive `ground_clearance_m`;
- a center z coordinate consistent with floor + clearance + half vehicle height.

The body remains a simplified parametric `OBST`, but it no longer touches the declared floor. The burner plane is the underbody plane.

### `IFC_BOUND`

Requires:

- explicit `source_entity_key`;
- a matching MappingPlan decision;
- the reviewed decision must keep `action=PASSIVE_OBSTACLE` for serialization authorization and explicitly carry `semantic_role=VEHICLE` for vehicle identity;
- verified source bounds;
- current P3a support requires the accepted base representation to be `OBST`;
- explicit `floor_z_m`;
- positive clearance derived from source bounds;
- requested clearance, when supplied, must match the source geometry.

The scenario fragment does **not** emit a duplicate vehicle body. It reuses the accepted base geometry and adds only the scenario burner plane plus trace metadata.

## Battery geometry

Battery geometry is optional but never invented.

It must be either:

1. bound to an explicit MappingPlan `source_entity_key`; or
2. supplied parametrically with explicit dimensions and center offset.

Resolved battery bounds must remain within the vehicle body envelope. P3a stores the battery bounds in the machine-readable `ScenarioBundle.vehicle_geometries`; it does not yet add independent battery thermal physics.

## IFC semantics and provenance

ISO 16739-1:2024 corresponds to the IFC 4.3 generation used as the scientific schema reference. IFC 4.3 contains the semantic entity `IfcVehicle` and `IfcVehicleTypeEnum` (including `VEHICLEWHEELED`). The project therefore must not infer vehicle identity from names when semantic source identity is available.

Authoritative buildingSMART reference:

- https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/annex-a-express.html

P3a binds by canonical `entity_key`, not fuzzy name matching. The bound decision must already be reviewed with `action=PASSIVE_OBSTACLE`, `review_status=APPROVED`, and `semantic_role=VEHICLE`. The obstacle action remains the serialization authorization; the semantic role is separate provenance for scenario binding. P3a does not infer vehicle identity from an object name. A source encoded in an older schema or as a generic proxy therefore requires an explicit reviewed mapping decision; this work package does not auto-promote it to `IfcVehicle`.

## Tests / scientific oracle

The software oracle is exact geometric arithmetic on resolved bounding boxes:

- `z_min - floor_z = ground_clearance`;
- IFC-bound center must equal the verified source-bound center;
- IFC-bound source must exist, retain passive-obstacle authorization, and carry reviewed `semantic_role=VEHICLE`;
- battery bounds must be contained by body bounds;
- P3 scientific modes place the burner at `z_min`, not `z_max`;
- legacy emission remains unchanged.

## Non-goals / remaining P3 work

This work package does **not** claim:

- orientation preservation for rotated/non-axis-aligned vehicles;
- vehicle-to-wall or vehicle-to-column collision acceptance;
- mesh adequacy across the underbody gap;
- battery thermal material correctness;
- validated EV fire physics.

Those remain required before `EV-GEO-001` can be raised beyond the exact scoped software evidence established here.

## Rollback

Revert the P3a commits. Because `geometry_mode=LEGACY` is the default and legacy output is regression-tested, reverting removes only the opt-in scientific geometry contract.
