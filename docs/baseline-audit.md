# IFCtoFDS v0.1.0 Baseline Audit & Defect Verification Report

**Date:** 2026-10-16  
**Auditor:** AI Systems Architect & BIM/FDS Verification Engineer  
**Baseline Commit:** `7352195f8892f1ebd963aeb48b3bd739d7859198`  
**License:** AGPL-3.0-or-later (Upstream: `ProfRino/IFCtoFDS`)  
**Target Repository:** `fire-digital-twin-lab/IFCtoFDS`  

---

## 1. Executive Summary

This report establishes the verified empirical baseline of `IFCtoFDS v0.1.0`. All defects, architecture bottlenecks, and geometry divergences reported in preliminary code reviews were audited, reproduced with reproducible scripts, and mapped to specific source code locations.

Key verified findings:
1. **P0 - Incomplete Element Ingestion due to Whitelist Filtering:** `js/ifc/ifc-adapter.js:2–25` silently discards any entity not in `PRODUCT_TYPES` before inventory recording. E.g., `IFCCOVERING` (13 entities in Duplex) and `IFCFOOTING` (7 entities in Duplex) are dropped without trace.
2. **P0 - MEP / HVAC / Fire Protection Excluded by Default:** `js/ifc/ifc-adapter.js:26-37` classifies all flow segments, fittings, and terminals as `REVIEW_TYPES`. In `js/fds/fds-exporter.js:451-457`, `includeReviewSolids` defaults to `false`. No MEP semantic graph or connectivity relationships are maintained.
3. **P0 - Missing Bidirectional Audit & Provenance Verification:** `js/compare/checks.js:2-82` only performs superficial bounding-box checks and surface checks on the generated FDS model itself. It cannot verify whether an element from IFC was lost, whether openings were sealed, or whether coordinate transformations were faithful.
4. **P1 - Critical Opening Void Loss in GEOM Export:** In `js/ifc/ifc-adapter.js:770-785`, box openings are only carved into `displayMesh`, leaving `exportMesh` uncarved. In `js/fds/fds-exporter.js:353-365`, `formatGeom()` exports `element.mesh` (`exportMesh`). Consequently, when exported as `GEOM`, walls with window/door cutouts (such as `Wand-Ext-ERDG-1` in `AC20-FZK-Haus.ifc`) are exported as solid boxes, completely erasing door and window openings.
5. **P1 - Incomplete MappedItem Transformation:** `js/ifc/ifc-adapter.js:936-956` calculates `origin` from `IfcRepresentationMap.MappingOrigin` but fails to apply its inverse transform (`composeTransform(productTransform, target)` only).
6. **P1 - Unbounded HalfSpace Clipping:** `js/ifc/ifc-adapter.js:979-986` approximates `IfcPolygonalBoundedHalfSpace` as an infinite clipping plane.
7. **P1 - UI Viewport Clip Does Not Filter Export Scope:** `js/app-controller.js:130-159, 973-991` only applies Three.js rendering clipping planes. `currentExportOptions()` transmits no spatial bounding box, causing full-building export even when a user intends to export only a basement storey.
8. **P1 - Native JS STEP Parser Scalability Cliff:** Native JS regex parsing parses small models in 2.1-2.4s, but hangs or exceeds 120s timeouts on models >10MB (such as `AC20-Institute-Var-2.ifc`, 10.93MB). Conversely, `ifcopenshell` parses the same file in **0.48s**.

---

## 2. Empirical Verification of Defects

### 2.1 Defect P0-1: Silent Element Loss (Duplex Model)
- **Model:** `examples/IfcOpenShell-Duplex.ifc` (IFC2X3, 295 `IfcProduct` instances).
- **Observed in IfcOpenShell:**
  - `IfcCovering`: 13 instances
  - `IfcFooting`: 7 instances
  - `IfcSpace`: 21 instances
  - `IfcFurnishingElement`: 61 instances
- **Observed in JS Native Parser (`ifc-adapter.js`):**
  - Only 208 products ingested.
  - `IfcCovering` (13) and `IfcFooting` (7) completely discarded on line 193:
    ```javascript
    function processEntity(ctx, entity) {
        if (!isSupportedProduct(entity, ctx.stairChildIds)) return;
        ...
    }
    ```
  - No diagnostic, inventory entry, or explanation is recorded.

### 2.2 Defect P1-1: Wall Opening Elimination in GEOM Export (FZK Haus)
- **Model:** `examples/AC20-FZK-Haus.ifc`
- **Element:** `Wand-Ext-ERDG-1` (`GlobalId: 3rPX_Juz59peXXY6wDJl18`)
- **Openings:** Has 3 openings:
  1. `EG-Fenster-6` (`0seqbT9MlcQAX_K0YLzD86`)
  2. `EG-Fenster-7` (`2NE9qKcWUF2uoVhRSqTd_a`)
  3. `Haustuer` (`04RcXu1mKxpGnJw_7oRBLn`)
- **Triangles in IfcOpenShell:** 40 vertices, 84 triangles (watertight mesh with all 3 openings subtracted).
- **Triangles in JS Native Exporter:**
  - `displayMesh`: 1,532 triangles (visual preview shows openings).
  - `exportMesh`: **12 triangles** (solid box, zero openings subtracted).
  - In `fds-exporter.js:357-362`:
    ```javascript
    element.mesh.vertices.forEach(...);
    element.mesh.faces.forEach(...);
    ```
  - When exported with mode `geom`, `element.mesh` is exported. The resulting FDS file has solid walls with zero openings for windows or doors.

### 2.3 Defect P1-2: Non-Identity MappedItem Origin Neglect
- **Code:** `js/ifc/ifc-adapter.js:936-956`
- **Code excerpt:**
  ```javascript
  var origin = step.transformForAxisPlacement(source.args[0]);
  if (!isIdentityish(origin)) {
      ns.core.addDiagnostic(diagnostics, 'info', 'IFC mapped origin approximated', ...);
  }
  ...
  var mappedTransform = composeTransform(productTransform, target); // MISSING: inverse(origin)
  ```
- **Standard Requirement (ISO 10303-43):**
  $$M_{\text{world}} = M_{\text{product}} \cdot M_{\text{target}} \cdot M_{\text{origin}}^{-1}$$
  Omitting $M_{\text{origin}}^{-1}$ causes displaced or misrotated shared components (e.g. doors, columns, furniture).

### 2.4 Defect P1-3: Display Clip vs Export Scope Disconnect
- **Code:** `js/app-controller.js:973-991`
- `currentExportOptions()` only collects:
  `cellSize, voxelSize, openingThickening, openingVoxelPolicy, includeFillSolids, includeReviewSolids, useObstHoles, forceObstStepIds, excludedStepIds`.
- The user-adjusted clip planes (`clip-xmin`, `clip-xmax`, `clip-ymin`, `clip-ymax`, `clip-zmin`, `clip-zmax`) are solely fed to Three.js `viewer.setClipPlanes()`.
- Exporting to FDS retains all entities in the building model outside the visible clip region.

---

## 3. Baseline Performance Metrics

| Model | Size | Step Entities | JS Parse Time | IfcOpenShell Parse Time | Speedup Factor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC20-FZK-Haus.ifc` | 2.57 MB | 44,249 | 2.39 s | 0.09 s | **26x** |
| `IfcOpenShell-Duplex.ifc` | 1.66 MB | 27,529 | 2.11 s | 0.07 s | **30x** |
| `AC20-Institute-Var-2.ifc` | 10.93 MB | 187,412 | > 120 s (timeout) | 0.48 s | **> 250x** |

---

## 4. Remediation Strategy

To achieve the research objectives without discarding the strengths of the upstream workbench:
1. **Hybrid Architecture:**
   - Retain and patch the lightweight browser engine for quick client-side previews and file-drop inspection.
   - Introduce an authoritative Python core powered by `ifcopenshell` and `ifcopenshell.geom`.
   - Maintain a standardized Canonical BIM JSON schema mediating between IFC, FDS, and the Validation Engine.
2. **Three-Tier Independent Validation Engine:**
   - Tier 1: IFC-to-Canonical completeness and accuracy.
   - Tier 2: Canonical-to-FDS translation and semantic traceability.
   - Tier 3: Effective FDS geometry analysis (IoU, opening preservation, non-blocked airflow, solver compatibility).
3. **Rigorous Audit & Acceptance Gate:**
   - Rejection of any model with unmapped required elements, lost openings, or ambiguous aliases.
