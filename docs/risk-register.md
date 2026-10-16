# Verified IFC-to-FDS Framework: Technical Risk Register

The table below is the initial framework risk register. For measured remediation status,
remaining solver blockers and actual evidence, see [review remediation](review-remediation.md).

| Risk ID | Level | Description | Impact | Mitigation Strategy | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | **P0** | Silent omission of non-standard IFC entity classes during parsing. | Critical structural elements or MEP equipment missing from simulation. | Implement 100% `IfcProduct` inventory auditing with explicit disposition codes for every element. | In Progress (Phase 1) |
| **RSK-02** | **P0** | Wall/slab openings lost in GEOM export mode. | Windows, doors, and vent openings sealed solid in FDS, invalidating smoke and fire flow. | 1. Patch JS native exporter to carve openings into `exportMesh`.<br>2. Use IfcOpenShell BRep boolean subtraction kernel as authoritative geometry source. | In Progress (Phase 2) |
| **RSK-03** | **P0** | HVAC / Fire Suppression components filtered out by default. | Ventilation ducts, exhaust dampers, and sprinkler heads omitted from FDS model. | Dedicated MEP extraction engine, graph connectivity extractor, and explicit mapping policies for flow components. | In Progress (Phase 3) |
| **RSK-04** | **P0** | Lack of independent verification gate. | Unaudited or corrupt FDS outputs exported and accepted as valid research models. | Three-tier independent validator auditing serialized FDS against source IFC model. | In Progress (Phase 5) |
| **RSK-05** | **P1** | Coordinate displacement from neglected `IfcRepresentationMap.MappingOrigin`. | Repeated components (doors, windows, columns) placed at incorrect coordinates or orientations. | Apply exact matrix transform $M_{\text{product}} \cdot M_{\text{target}} \cdot M_{\text{origin}}^{-1}$ in both JS and Python geometry engines. | In Progress (Phase 2) |
| **RSK-06** | **P1** | Infinite planar clipping of `IfcPolygonalBoundedHalfSpace`. | Over-clipping walls under complex roofs. | Integrate IfcOpenShell OpenCASCADE-based solid booleans for exact bounded clipping. | In Progress (Phase 2) |
| **RSK-07** | **P1** | Viewport clipping does not filter export scope. | Full building exported when user intends to simulate only a basement or fire compartment. | Decouple UI rendering clip from true geometric export bounding box filter in `currentExportOptions()`. | In Progress (Phase 4) |
| **RSK-08** | **P1** | Native JS parser scalability failure on large IFC files (>10MB). | Browser crashes or hangs during conversion of realistic multi-storey or facility models. | Route heavy processing through Python `IfcOpenShell` backend with fast C++ parser (~0.5s for 11MB file). | Not yet accepted; benchmark includes timeouts |
| **RSK-09** | **P2** | Incomplete unit conversion for imperial / non-standard IFC models. | Scaled geometry ten-fold or hundred-fold off in FDS. | Explicit parse of `IfcUnitAssignment` and conversion factors to standard SI meters. | In Progress (Phase 1) |
| **RSK-10** | **P2** | External CDN dependencies (Three.js, Lucide) breaking offline / air-gapped usage. | Workbench unavailable in restricted environments. | Bundle essential vendor assets locally or support self-contained serving. | In Progress (Phase 6) |
