# 04 — Domain Model Architecture

The Domain Core is divided into 7 bounded contexts:

## 1. Source Domain (`domain/source/`)
- `SourceMetadata`: File metadata, schema version, unit scale, world placement matrix, SHA-256 hash.
- `SourceIdentity`: Multi-IFC identity addressing (`source_id:step_id` or `source_id:global_id`).
- `ExecutionEnvironment`: Tool version, git SHA, schema version, runtime library versions.

## 2. BIM / Canonical Domain (`domain/bim/`)
- `CanonicalModel`: Aggregated canonical representation of the BIM model.
- `CanonicalElement`: Normalized element representation without live IfcOpenShell entity references.
- `BoundingBox`: 3D bounding box with finite positive extents and XB conversions.
- `TriangleMesh`: Explicit vertex and index lists with manifold and normal checks.
- `OpeningReference`: Explicit opening void definition and host carving state.
- `StoreyReference`: Normalized storey elevation and spatial containment.

## 3. Scope Domain (`domain/scope/`)
Strict separation of 3 independent concepts:
1. `SelectionScope`: Which storeys or spatial bounds the user selected (`IN_SCOPE`, `OUT_OF_SCOPE`).
2. `SimulationDomain`: The physical coordinate bounds where FDS computes the fire simulation.
3. `BoundaryPolicy`: How cross-boundary elements intersecting the simulation domain are treated (`PRESERVE_AND_BLOCK`, `PENDING_VALIDATION`).

## 4. MEP Domain (`domain/mep/`)
- `MEPElement`: Categorized MEP component.
- `MEPSystem`: Distribution system with fire-safety critical flagging.
- `PortReference`: Source-qualified port identity, flow direction, world coordinates.
- `MEPConnection`: Topology connection edge between ports.
- Separation of `SemanticRole` (HVAC_DUCT) vs `SimulationRole` (REFERENCE_GEOMETRY vs PASSIVE_OBSTACLE).

## 5. Mapping Domain (`domain/mapping/`)
- `MappingDecision`: Concrete strategy and representation chosen for an element.
- `MappingPlan`: Immutable collection of mapping decisions produced by domain policies before serialization.
- `MappingStrategy`: OBST, GEOM, VOXEL, SEMANTIC_ONLY, EXCLUDED_APPROVED.

## 6. Validation Domain (`domain/validation/`)
- `Finding`: Individual validation finding with category, severity, element_id, rule_id, details.
- `GateStatus`: `PASS`, `FAIL`, `INCONCLUSIVE`, `NOT_APPLICABLE`, `NOT_RUN`.
- `GateResult`: Status, brief reason, metrics, findings, evidence references.
- `AcceptanceReport`: Immutable finalized report object containing the acceptance verdict (`MAPPING_VERIFIED`, `INCONCLUSIVE`, `REJECTED`).

## 7. Reference Domain (`domain/reference/`)
- `GoldenReference`: Approved ground truth specification.
- `ReferenceCandidate`: Draft candidate bundle requiring explicit human-in-the-loop approval.
- `IntentionalDelta`: Documented and accepted discrepancies against reference cases.
