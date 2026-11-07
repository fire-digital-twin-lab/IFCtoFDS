# P3a — Vehicle identity and ground-clearance geometry contract

**Scoped P3a status:** `PASS (E2)` on code candidate `6169b55321d6c7404d7b1a39d3633f3aef2733a9`; full P3 / `EV-GEO-001` remains `FAIL`  
**Roadmap phase:** P3 — Vehicle identity & geometry  
**Scientific claims:** scoped `EV-GEO-P3A-001 = PASS / E2`; broad `EV-GEO-001 = FAIL`  
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

1. bound to an explicit MappingPlan `source_entity_key` whose reviewed decision carries `semantic_role=BATTERY_PACK` and passive-obstacle authorization; or
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
- IFC-bound battery source must carry reviewed `semantic_role=BATTERY_PACK`;
- battery bounds must be contained by body bounds;
- P3 scientific modes place the burner at `z_min`, not `z_max`;
- legacy emission remains unchanged.

The geometric comparison tolerance is `1e-4 m`. This tolerance is used for source-center and declared-clearance consistency checks; it is not a CFD mesh tolerance and does not replace post-snap/grid sensitivity evidence.

## FDS 6.11.1 contract correction discovered during P3a

Pinned FDS execution found a pre-existing parser/emitter drift: `SURF.FUEL_ID` was accepted by the project parser but rejected by FDS 6.11.1. P3a therefore corrected the scientific contract instead of weakening the solver gate:

- scientific `PARAMETRIC` / `IFC_BOUND` burner surfaces emit `HRRPUA` + `RAMP_Q` without `FUEL_ID`;
- the default parser rejects `SURF.FUEL_ID` as unsupported;
- `allow_legacy_surf_fuel_id=True` is an explicit compatibility-only switch for historical LEGACY fragments;
- scientific emitter/composer/physics paths fail closed on parser `errors` or `unsupported` fields;
- LEGACY serialization remains unchanged by default.

This correction is evidence about syntax/integration, not about the physical adequacy of the EV fuel chemistry.

## Solver and CI evidence

Code candidate: `6169b55321d6c7404d7b1a39d3633f3aef2733a9`.

- Source quality run `42380373024`: PASS; full Python quality `879 passed, 14 deselected`, coverage `87%`.
- Source-quality artifact `13577831468`: `sha256:37b0be1cc4c529a94cb5eaf2b96ff09727798c654598d3651c099b114eec23a9`.
- Conversion run `42380373058`: PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS.
- Solver job: `9 passed, 884 deselected`.
- Solver artifact `13577781396`: `sha256:686ada474718c4261eeac039d4548c1ce75453b50cdf5a3aa042c44701861c9c`.

The P3a solver fixture runs FDS 6.11.1 for `0.1 s` instead of accepting a set-up-only exit. Its mesh is `IJK=20,20,40`, `XB=2.5,7.5,4.0,6.0,0.0,2.0`, giving `dx=0.25 m`, `dy=0.10 m`, `dz=0.05 m`. Therefore the 0.15 m parametric gap has 3 vertical cells and the 0.20 m IFC-bound gap has 4 vertical cells. This only establishes scoped solver acceptance of the generated geometry; it is not a P4 mesh-adequacy or grid-sensitivity claim.

The solver logs retain two warnings:

1. FDS recommends defining the REAC fuel chemistry with SPEC.
2. The generated OFFGAS species is not in the built-in species table.

Those warnings are not fatal for the scoped geometry acceptance, but they remain explicit P6 physics findings. They prevent interpreting the P3a solver run as validated EV combustion/species physics.

## Non-goals / remaining P3 work

This work package does **not** claim:

- orientation preservation for rotated/non-axis-aligned vehicles;
- vehicle-to-wall or vehicle-to-column collision acceptance;
- production/local MeshPlan adequacy, post-snap clearance and coarse/medium/fine grid sensitivity;
- battery thermal material correctness;
- validated EV fire physics, including the current REAC/OFFGAS warnings;
- jet-outlet geometry and directional underbody jet representation.

Automatic promotion from native IFC `IfcVehicle` semantics is also not implemented in P3a; binding requires an explicit reviewed decision. Those items remain required before `EV-GEO-001` can be raised beyond the exact scoped software evidence established here.

## Rollback

Revert the P3a commits. Because `geometry_mode=LEGACY` is the default and legacy output is regression-tested, reverting removes only the opt-in scientific geometry contract.

## Scoped verdict

`EV-GEO-P3A-001 = PASS / E2` for the exact axis-aligned software and solver-integration contract described above.

`EV-GEO-001 = FAIL` remains unchanged because the broad P3 claim includes orientation preservation, complete collision acceptance, jet outlets, post-snap/local-mesh clearance and application evidence that P3a does not provide.

No result in this work package establishes solution verification, model validation, application validation, fire-safety compliance, or `SIMULATION_VERIFIED`.
