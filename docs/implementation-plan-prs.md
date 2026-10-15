# Verified IFC-to-FDS Framework: Implementation & PR Roadmap

This document outlines the sequential Pull Request roadmap, technical scope, and strict acceptance criteria for each phase.

---

## PR 1: Baseline Architecture & Quick Geometry Fixes (Phase 0 & JS Fixes)
- **Scope:**
  - Audit report, architecture specification, risk register.
  - Fix wall opening loss in JS `carveItemOpenings` and `exportMesh` (`js/ifc/ifc-adapter.js`).
  - Fix `exportGeom()` in `js/fds/fds-exporter.js` to prioritize carved geometry.
  - Fix `meshForMappedItem()` in `js/ifc/ifc-adapter.js` to calculate inverse of `MappingOrigin`.
  - Expand `PRODUCT_TYPES` to include `IFCCOVERING`, `IFCFOOTING`, `IFCRAMP`, `IFCFLOWCONTROLLER`, etc.
  - Regression unit tests for opening retention on `Wand-Ext-ERDG-1`.
- **Acceptance Criteria:**
  - `Wand-Ext-ERDG-1` in `AC20-FZK-Haus.ifc` retains 3 openings when exported in `all-GEOM` mode.
  - Zero regression in background export worker test.

---

## PR 2: Authoritative Python IFC Core & Canonical Schema (Phase 1 & 2)
- **Scope:**
  - Directory structure `ifc_to_fds/core/` and `ifc_to_fds/geometry/`.
  - Canonical BIM Schema (Pydantic models, JSON serialization).
  - 100% `IfcProduct` inventory accounting with source SHA-256 and disposition tracking.
  - Unit assignment conversion to meters.
  - Geometry kernel leveraging `ifcopenshell.geom.iterator` and BRep boolean processor.
  - Manifold mesh extraction, vertex deduplication, and normal consistency checks.
- **Acceptance Criteria:**
  - Ingestion of 295 `IfcProduct` entities in `IfcOpenShell-Duplex.ifc` with 0 unhandled entities.
  - Complete geometric shape generation for `AC20-FZK-Haus.ifc` with watertight opening subtractions.
  - Python test suite passing with `pytest`.

---

## PR 3: MEP / HVAC & Fire Protection Engine (Phase 3)
- **Scope:**
  - `ifc_to_fds/mep/classifier.py` and `ifc_to_fds/mep/mep_graph.py`.
  - Identification of ventilation, smoke extraction, and fire suppression systems (`IfcRelAssignsToGroup`).
  - Extraction of flow segments (ducts, pipes), fittings (elbows, tees, reducers), terminals (air terminals, sprinklers), and controllers (dampers, valves).
  - Topological connectivity extraction via `IfcRelConnectsPorts` and port placement.
  - Explicit vs. proximity-inferred connection differentiation.
- **Acceptance Criteria:**
  - Extraction of all MEP elements in test models.
  - Generation of structured MEP Graph JSON with coverage statistics.

---

## PR 4: FDS Mapping Policy Engine & Spatial Scope (Phase 4)
- **Scope:**
  - `ifc_to_fds/mapping/policy.py`, `scope.py`, `exporter.py`, and `manifest.py`.
  - Mapping policies: `OBST`, `OBST+HOLE`, `GEOM`, `SEMANTIC_ONLY`, `EXCLUDED_APPROVED`.
  - Spatial scoping: Bounding box clipping and Storey filtering without accidental omission of connecting stairs/shafts.
  - FDS file emitter formatting namelists, SURF_IDs, and inlined `! IFC_SOURCE` provenance comments.
  - Bidirectional mapping manifest linking every IFC `GlobalId` to generated FDS primitive IDs.
- **Acceptance Criteria:**
  - Generation of valid `.fds` syntax conforming to FDS 6+ specifications.
  - Mapping manifest accounts for 100% of elements in the selected scope.

---

## PR 5: Independent Validation Engine & Acceptance Gate (Phase 5)
- **Scope:**
  - `ifc_to_fds/validation/engine.py`, `metrics.py`, and `acceptance.py`.
  - Tier 1: IFC $\rightarrow$ Canonical audit.
  - Tier 2: Canonical $\rightarrow$ FDS audit.
  - Tier 3: Effective FDS geometry & airflow clearance audit.
  - Mutation tests demonstrating detection of artificially removed or deformed primitives.
  - Acceptance report generator producing JSON and Markdown summaries.
- **Acceptance Criteria:**
  - Validator flags intentional mutations (e.g., deleted door hole or blocked vent).
  - Clear `VERIFIED` or `REJECTED` verdict with actionable diagnostic findings.

---

## PR 6: Web Workbench Integration & Local Backend (Phase 6)
- **Scope:**
  - `ifc_to_fds/server.py`: FastAPI server endpoints (`/api/convert`, `/api/inventory`, `/api/audit`, `/api/health`).
  - Frontend updates in `index.html` and `js/app-controller.js`:
    - "Verified Conversion" button calling local backend.
    - True Spatial Scope filter controls.
    - Source Inventory Tree and MEP System layer toggles.
    - Audit Dashboard displaying acceptance status and findings.
- **Acceptance Criteria:**
  - End-to-end execution from browser file selection to verified FDS download and report view.

---

## PR 7: Performance Benchmarking & Release Verification (Phase 7 & 8)
- **Scope:**
  - Benchmark suite comparing JS Native vs. Verified Python Pipeline across FZK Haus, Duplex, and Institute.
  - Measurement of parse time, memory usage, IoU, and opening retention.
  - Documentation updates: User guide, developer manual, API references.
- **Acceptance Criteria:**
  - Benchmark results documented and reproducible via automated script.
  - Full documentation complete with AGPL-3.0 attribution maintained.
