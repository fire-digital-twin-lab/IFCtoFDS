# Verified IFC-to-FDS Mapping Framework: System Architecture

**Version:** 0.3.0-dev
**Status:** Development; GEOM effective geometry remains incomplete. See [current limitations](verified-conversion.md).
**Base Repository:** `fire-digital-twin-lab/IFCtoFDS`  
**Upstream:** `ProfRino/IFCtoFDS`  

---

## 1. Architectural Principles

1. **Deterministic Traceability:** Every FDS primitive (`&OBST`, `&HOLE`, `&GEOM`, `&VENT`) must link back to one or more explicit IFC source entities (`GlobalId`, STEP ID, class, storey, system), or be labeled as an algorithmic auxiliary primitive.
2. **Canonical Intermediate Representation:** IFC ingestion is decoupled from FDS serialization through a strongly-typed **Canonical BIM Model**. The geometry engine does not generate FDS syntax directly; it produces a normalized topological and semantic graph.
3. **No Silent Omissions:** Every `IfcProduct` in the source model must receive a recorded disposition status (`MATCHED`, `DEVIATED`, `SEMANTIC_ONLY`, `EXCLUDED_APPROVED`, `UNSUPPORTED`, `MISSING_SOURCE_DATA`).
4. **Independent Verification:** The validation engine cannot rely on intermediate exporter structures; it audits the deserialized final FDS file against the source IFC model.
5. **Dual-Mode Workflow:**
   - **Quick Conversion (Client-Side / JS):** Fast browser-only preview and initial check.
   - **Verified Conversion (Authoritative / Python + IfcOpenShell):** Rigorous geometry BRep kernel, full MEP graph extraction, spatial scoping, bidirectional manifest generation, and acceptance gating.

---

## 2. End-to-End Dataflow

```
                    ┌──────────────────────────────────────────────┐
                    │               Source IFC Model               │
                    │   (STEP / IFC2X3, IFC4, IFC4X3, SHA-256)     │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │      IfcOpenShell Authoritative Parser       │
                    │   - Unit Normalization (SI -> Meters)        │
                    │   - ObjectPlacement & Coordinate Transforms  │
                    │   - 100% IfcProduct & Spatial Ingestion      │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │             Canonical BIM Model              │
                    │   - Structural Elements & Watertight Meshes  │
                    │   - MEP Flow Segments, Fittings, Terminals   │
                    │   - Port & Connectivity Topology Graph       │
                    │   - Property Sets, Storeys, Systems          │
                    └──────────────────────┬───────────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
     ┌────────────────────────────────────┐ ┌────────────────────────────────────┐
     │      Spatial Scope Filter          │ │      MEP System Classifier         │
     │ - Real Bounding Box / Slice        │ │ - Ventilation & Smoke Extract      │
     │ - Storey / Zone Filtering          │ │ - Fire Suppression (Sprinkler/FP)  │
     │ - Cross-boundary element handling  │ │ - Explicit vs Spatial Connectivity │
     └──────────────────┬─────────────────┘ └─────────────────┬──────────────────┘
                        │                                     │
                        └──────────────────┬──────────────────┘
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │         FDS Mapping Policy Engine            │
                    │ - OBST (Prisms & Flat Slabs)                 │
                    │ - OBST + HOLE (Axis-aligned walls/windows)   │
                    │ - GEOM (Valid Complex Solids)     │
                    │ - SEMANTIC_ONLY (Flow graphs, metadata)      │
                    │ - EXCLUDED_APPROVED (Documented exclusions)  │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │               FDS Serializer                 │
                    │ - Standardized .fds (MESH, OBST, HOLE, GEOM) │
                    │ - Inlined IFC_SOURCE Provenance Comments     │
                    │ - Bidirectional Mapping Manifest (JSON/CSV)  │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │     Independent Validation Engine            │
                    │ - Tier 1: IFC -> Canonical Completeness      │
                    │ - Tier 2: Canonical -> FDS Mapping Fidelity   │
                    │ - Tier 3: Effective Geometry & Airflow Audit │
                    └──────────────────────┬───────────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
     ┌────────────────────────────────────┐ ┌────────────────────────────────────┐
     │       Acceptance Gate & Report     │ │     Web UI & Visualization         │
     │ - VERIFIED / REJECTED / INCONCLUSIVE      │ │ - Overlay View & Diff Highlighting │
     │ - IoU, Deviation, Topology metrics │ │ - Element Provenance Inspector     │
     │ - Detailed Findings (P0-P3)        │ │ - Export FDS + Manifest + Report   │
     └────────────────────────────────────┘ └────────────────────────────────────┘
```

---

## 3. Component Architecture

### 3.1 Python Package: `ifc_to_fds`
Located at `ifc_to_fds/`:
- `core/`:
  - `canonical.py`: Canonical BIM Model Schema (Pydantic models, JSON serialization).
  - `inventory.py`: Complete source entity accounting.
  - `units.py`: Unit assignment parsing and meter scaling factors.
  - `placement.py`: Multi-level placement resolution and coordinate transformations.
- `geometry/`:
  - `engine.py`: IfcOpenShell geometry kernel integration using `ifcopenshell.geom.iterator` and `create_shape`.
  - `mesh.py`: Triangle mesh representation, bounding boxes, manifold and normal consistency audits.
  - `openings.py`: Host-opening relation resolution, boolean difference subtraction, and boundary void preservation.
- `mep/`:
  - `classifier.py`: Classification of ductwork, pipework, fire suppression terminals, and dampers.
  - `mep_graph.py`: Extraction of port connections (`IfcRelConnectsPorts`), system assignments (`IfcRelAssignsToGroup`), and directional flow topology.
- `mapping/`:
  - `policy.py`: Mapping strategy selector (OBST, OBST+HOLE, GEOM, SEMANTIC_ONLY, EXCLUDED_APPROVED).
  - `scope.py`: Spatial filter clipping elements by 3D box or storey selection with boundary retention rationale.
  - `exporter.py`: FDS serialization with structured comments and standard namelists.
  - `manifest.py`: Bidirectional IFC $\leftrightarrow$ FDS manifest generation.
- `validation/`:
  - `engine.py`: Three-tier verification orchestrator.
  - `metrics.py`: Calculation of Intersection over Union (IoU), Hausdorff surface distance, and opening retention rates.
  - `acceptance.py`: Strict acceptance criteria evaluation and report emission.
- `cli.py`: Command-line interface for headless execution and batch CI/CD pipelines.
- `server.py`: Lightweight FastAPI application providing local REST endpoints for the Web workbench.

### 3.2 Client-Side Web Workbench: `js/`
- Retains existing Three.js rendering in `js/viewer/scene-viewer.js`.
- Fixes native JS geometry bugs (GEOM opening subtraction and MappedItem origins) in `js/ifc/ifc-adapter.js` and `js/fds/fds-exporter.js`.
- Adds UI controls in `index.html` and `js/app-controller.js` for:
  - Real Spatial Scope (Export Scope vs. Viewer Clip).
  - MEP System inspection and layer toggling.
  - Verified Conversion action invoking the Python backend.
  - Acceptance Report display and issue remediation alerts.

---

## 4. Canonical Model Schema Specification

The Canonical Model stores normalized building objects in standard SI units (meters) under a unified Cartesian frame:

```json
{
  "source": {
    "filename": "building.ifc",
    "file_hash_sha256": "abcdef123456...",
    "schema": "IFC4",
    "unit_scale_to_meters": 1.0
  },
  "inventory": [
    {
      "global_id": "3rPX_Juz59peXXY6wDJl18",
      "step_id": 412,
      "ifc_type": "IfcWallStandardCase",
      "name": "Wand-Ext-ERDG-1",
      "storey": "Level 0",
      "systems": [],
      "disposition": "MAPPED",
      "mapping_strategy": "GEOM",
      "bounding_box": [0.0, 10.0, 0.0, 0.3, 0.0, 2.8],
      "mesh_ref": "mesh_412",
      "openings": [
        {
          "opening_global_id": "0seqbT9MlcQAX_K0YLzD86",
          "opening_name": "EG-Fenster-6",
          "bounding_box": [1.5, 3.0, -0.05, 0.35, 1.0, 2.2]
        }
      ]
    }
  ],
  "mep_graph": {
    "systems": [
      {
        "system_id": "sys_smoke_extract_01",
        "name": "Basement Smoke Extract",
        "system_type": "VENTILATION",
        "element_ids": ["3rPX_...", "0seq..."]
      }
    ],
    "connections": [
      {
        "source_port": "port_1",
        "target_port": "port_2",
        "connection_type": "EXPLICIT_RELATION"
      }
    ]
  }
}
```

---

## 5. Three-Tier Validation Engine

| Tier | Scope | Verifications | Acceptance Condition |
| :--- | :--- | :--- | :--- |
| **Tier 1: IFC $\rightarrow$ Canonical** | Source Coverage | Ingest 100% of `IfcProduct`. Verify unit scaling, geometry manifoldness, and opening extraction. | Zero unhandled P0/P1 classes. 100% accounting in inventory. |
| **Tier 2: Canonical $\rightarrow$ FDS** | Semantic & Syntax Translation | Verify every mapped element has valid FDS primitives, bounds match within tolerance ($\epsilon \le 1$ mm), openings are cut, and metadata is inlined. | 100% provenance traceability. Zero lost openings. |
| **Tier 3: Effective Geometry** | Physics & Simulation Integrity | Parse serialized FDS. Check mesh alignment, detect unintentional blocked airflow passages, audit closed fill perimeters, verify non-degenerate OBST/GEOM. | No degenerate geometries. Openings preserve clear transit paths. |
