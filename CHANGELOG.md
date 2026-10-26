# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] — 2026-10-26

Major release delivering the research-grade Python Verified Pipeline, 14-gate independent audit engine, and EV battery fire simulation suite.

### Added
- **Verified Python Pipeline**: Native IfcOpenShell OpenCASCADE geometry extraction with 64-bit float precision and strict rejection of open/non-manifold sheets without phantom bounding-box substitution.
- **14-Gate Independent Audit Engine**: Fully independent source re-reading from disk, verifying syntax, domain extents, provenance traceability, enclosure airtightness (`air_path`), opening preservation, structural completeness, MEP port connectivity, and solver compatibility.
- **EV Battery Fire Scenario Emitter**: Standardized $t^2$ fire growth curves ($Q = 1055 \cdot (t/t_\alpha)^2$), 20-point RAMP discretization, composite single `&REAC` for FDS simple chemistry, passive `&SPEC` tracer for toxic HF offgas, battery pack energy balance, and FDS Section 15.3 door control semantics.
- **Multi-Mesh Grid Partitioning**: Automated domain partitioning (`partition_simulation_domain`) splitting domains $> 500,000$ cells into aligned submeshes along X/Y axes for FDS MPI parallel processing.
- **A Priori Opening Heuristic**: Geometric preflight checker (`check_opening_grid_alignment`) warning when opening width $< 2 \cdot dx$ to detect openings at risk of grid closure.
- **Audit Remediation**: Complete fixes for audit findings C-1 through C-3, H-1 through H-13, and M-6 through M-11.

### Changed
- Job lifecycle API contract: `POST /api/jobs/{jid}/cancel` is idempotent and never purges artifacts. `DELETE /api/jobs/{jid}` requires `?purge=true` to delete artifacts of terminal jobs.
- Result API supports pagination via `offset` and `limit` query parameters, preserving all findings without truncation.
- Artifact listings on `/api/jobs/{jid}/result` filter dynamically to include only files actually produced on disk.

## [0.4.0] — 2026-09-15

### Added
- Hexagonal architecture (Ports & Adapters) formalization (ADR-002) with architectural boundary verification tests via AST.
- SQLite WAL asynchronous job manager (`JobService`, `JobRepository`) with process-level isolation and RSS memory supervision.
- Streaming geometric payloads packaging (`write_package`) using SHA-256 content-addressable binary blobs.

## [0.3.0] — 2026-08-10

### Added
- 12-gate independent audit framework with fail-closed acceptance criteria.
- Manifold3D Binary64 Boolean CSG backend for precise void subtraction.
- Spatial scoping and coordinate rebase vector normalization.

## [0.2.0] — 2026-07-05

### Added
- Python Verified Pipeline (`ifc_to_fds`) incorporating IfcOpenShell and OpenCASCADE mesh evaluation.
- Multi-file IFC federation and transform concatenation.
- MEP port connectivity extraction and graph topology mapping.

## [0.1.0] — 2026-06-02

Initial public release.

### Conversion

- Native IFC parser handling `IfcExtrudedAreaSolid`, `IfcFacetedBrep`,
  `IfcTriangulatedFaceSet`, `IfcFaceBasedSurfaceModel`, planar
  `IfcBooleanClippingResult` cuts, and `IfcRelVoidsElement` openings — no
  server or WASM required.
- Two opening strategies selectable from the UI:
  - **HOLE (recommended)** — one continuous `&OBST` per axis-aligned wall/slab
    plus rectangular `&HOLE` cutouts.
  - **Voxelization (legacy)** — stair-stepped `&OBST` cluster around each
    opening, for arched / curved geometry that `&HOLE` cannot represent.
- Optional closed window/door fills emitted as colored airtight `&OBST`s
  (window blue / door brown). With HOLE, closures are deferred to the end of
  the namelist so wall `&HOLE`s cannot carve the glass.
- Non-convex BREP outlines (L, U, T floor plates) re-triangulated with
  Mapbox earcut, replacing a fan triangulation that used to collapse them to
  their bounding rectangle.
- Flat slabs whose IFC representation the parser couldn't extrude are
  auto-inflated to a default thickness so their outline is preserved through
  voxelization.
- Bbox-based opening carve eliminates the 1-cell "phantom gap" that the
  ray-casting point-in-mesh test left at axis-aligned opening corners.

### Viewer

- Three.js scene with three view modes (Overlay / FDS / IFC), independent
  opacity sliders, and per-layer toggles for OBST, HOLE, VENT, GEOM, and
  IFC categories.
- HOLE markers render as ghost-cyan boxes so the closure colour behind them
  shows through. Window/door closure OBSTs render 12 mm proud of the wall
  plane to avoid z-fight flicker.
- GEOMs render distinctly darker than OBSTs so the two output kinds are easy
  to tell apart.
- Six clip-bar sliders at the bottom of the viewer cut the scene to a
  sub-volume. FDS primitives whose full bbox sits inside the clip stay
  visible; the rest disappear cleanly (no slicing through).
- First-person walk mode (footprint icon) with click-to-place. The click
  raycasts down to find the actual floor under the cursor, not the first
  surface the ray crosses. Door closures and HOLE volumes are passable so
  you can step through doorways.
- Distance-first click pick — clicking a visible front wall lands on that
  wall instead of a HOLE behind it. HOLE/VENT priority still wins as a
  tie-breaker within 0.3 m.
- Marquee multi-selection with **Shift + drag**.
- Conversion reveal animation with linear sweep that scales duration with
  building height (caps at 6 s).
- Keyboard navigation: `1`–`6` / `0` snap to canonical views; arrow keys
  orbit; `Shift` + arrows dolly or strafe; `Ctrl + Z` undo.

### App

- Background Web Worker conversion with per-element progress on the top
  banner so the UI stays responsive on large IFCs.
- Inline worker bundle for `file://` (direct double-click) origin.
- Delete-selected / undo / per-primitive OBST removal.
- Top-banner loading indicator during both IFC parse and FDS export.
- Single-column `guide.html` page linked from the help icon in the toolbar.

### Tooling

- `node scripts/test-ifc-conversion.js` exercises the bundled IFCs through
  the full export pipeline and regenerates the inline worker bundles.

### Bundled examples

- `examples/AC20-FZK-Haus.ifc` (KIT, via STEP Tools)
- `examples/AC20-Institute-Var-2.ifc` (KIT, via STEP Tools)
- `examples/IfcOpenShell-Duplex.ifc` (IfcOpenShell voxelization toolkit)

[0.1.0]: https://github.com/ProfRino/IFCtoFDS/releases/tag/v0.1.0
