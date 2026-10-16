# Golden mapping remediation — delivery status (2026-10-16)

Base: origin/codex/verified-correctness at 1611615d86af2c9dd5cda98b67820a2feeaba82a.
Branch: codex/golden-mapping-parity. The base was fetched before branch creation.

## Implemented and checked

- Canonical/manifest/report 0.4 with independent presence, geometry, role,
  operational, representation, review and boundary fields.
- Building-qualified storey intervals; explicit fixed scoped domain; no MESH
  expansion, automatic clipping, cap creation or MEP topology removal.
- Review objects no longer auto-approved for exclusion. MEP reference meshes are
  saved and independently audited outside FDS; type-based IFC2X3 classification.
- Geometry package with identity/transform/opening/port evidence and checksums.
- Mapping and simulation outcomes separated; boundary evidence still blocks mapping.
- Content-bound draft/approved reference loader, explicit deltas, geometry-backed
  alias checks, direct accepted/current FDS solid and passage parity, semantic/network parity and entity-specific mutations.
- CLI/API profiles, registered server references, new artifact downloads and
  reference geometry viewer group; original upload filename preserved.
- Inventory-only private intake, optional explicit external acceptance runner,
  CI regressions and bounded Quick audit in the benchmark harness.

The full local Python suite passed **89 tests**, with one real-solver test
intentionally deselected. Existing trimesh zero-volume warnings and the Starlette
TestClient deprecation remain visible. Ruff format/check and git diff checks passed.
JavaScript workflow, export completeness/opening rays, GEOM openings and export
worker regressions passed; regenerated worker bundles match committed sources.

The live Edge headless check selected a qualified storey and fixed domain, ran an
isolated job, displayed MAPPING_VERIFIED / simulation INCONCLUSIVE, and exposed
seven artifact downloads with zero page errors. Screenshot is an ignored local
artifact at scripts/out/golden-ui/mapping.png. The analytic tiny fixture verifies
UI integration; it is not evidence that the private basement model is accepted.

The source context import verified all **32/32 supplied SHA256 entries**. The
pre-existing root hash index remains untracked and unmodified.

## Real source intake (not accepted reference)

ALL_FDS_2027.ifc is an external local source, SHA256
`a54ba512754efe1f82b87d7fb1853361889ad00d59be5a7a14ecac075e2cc7af`, IFC2X3,
31,645,383 bytes, FOOT scale 0.3048.

Inventory: 5,641 IfcProduct, five buildings, 63 storeys, 180 proxies, 2,392 ports,
1,068 explicit connection relations and 1,068 saved edges. Type-aware provisional
classification yields 942 ventilation candidates, 588 plumbing candidates and 180
unresolved physical proxy candidates. These are whole-file results, not accepted
B1/B2 coverage. Plumbing candidates are not asserted to exclude FP; system-specific
classification still needs source evidence and case review. The historical FP
124/120/4 figures remain unvalidated and are not hardcoded expectations.

Detailed model-derived inventories/graphs stay under .local-reference-cases/.
The tracked basement reference is an empty DRAFT template bound to source hash;
its empty expected inventory is not a claim of zero source elements. No IFC or
historical accepted FDS has been published by this change.

## Remaining acceptance conditions

The software mechanisms and synthetic regressions can run. Real-project acceptance
is still INCONCLUSIVE until the team supplies or reviews:

1. Exact B1/B2 building/storey groupings and independently justified simulation domain.
2. Structural/MEP roles, exclusions, unresolved proxies and local system classifications.
3. Historical accepted FDS/decisions, or a newly reviewed baseline explicitly identified as new.
4. Actual real-source geometry/passage audits and reference approval tied to its digest.
5. Validated boundary representations and pinned solver/effective-geometry evidence.

No boundary policy is silently considered validated in this implementation.
No full private-model geometry conversion or scientific benchmark is claimed.
The optional benchmark smoke run is harness validation only. GEOM cut-cell,
HOLE/VENT and multi-mesh effective geometry limitations remain. Operational physics
and SIMULATION_VERIFIED are outside this stage. Do not merge dev/main as if the
basement reference or full simulation were accepted.

Current contracts: [mapping/parity guide](golden-mapping-parity.md).
Decision change: [ADR 0004](adr/0004-golden-domain-and-mep-roles.md).

## Requirement to regression evidence

| Requirement | Regression |
|---|---|
| Fixed domain and no crossing-element loss | domain_does_not_follow_boundary_extent |
| Storeys isolated by building | storey_interval_is_within_building |
| Spatial items are not physical obstacles | scoped_explicit_domain_ignores_spatial_entities_as_obstacles |
| No silent scope exclusion after geometry failure | failed_geometry_cannot_be_declared_outside_scope |
| Proxy review / reference-only MEP | proxy_and_reference_mep_do_not_become_obstacles |
| Missing saved geometry detected after rehash | reference_mesh_mutation_even_after_rehash |
| Independent file audit / old schema | independent_file_audit_and_legacy; legacy_report_is_not_promoted |
| Exact missing/extra/role/source/geometry detection | golden_mutations |
| Actual FDS opening sealed | golden_resealed_actual_fds |
| Missing explicit connection | golden_network_missing_edge |
| Alias proof and explicit delta | alias_requires_actual_geometry_proof; delta_is_explicit_and_does_not_waive_gate |
| Semantically equivalent mesh ordering | mesh_equivalence_without_vertex_or_face_order |
| Coordinate order cannot hide a changed port/transform | reference_port_coordinate_permutation_is_detected; source_transform_axis_permutation_is_not_equivalent |
| Golden geometry compared directly to accepted FDS | golden_compares_actual_fds_to_accepted_fds |
| Manual FDS import remains unapproved | manual_fds_import_stays_a_draft |
| Draft and edited reference cannot pass | golden_positive_and_draft; golden_bundle_edit_rejected |
| Mapping vs simulation | mapping_and_simulation_levels |
| Registered server paths only | reference_paths_are_operator_registered |
| Web domains/roles/artifacts | test-golden-workflow.js; qa-golden-browser.py |
