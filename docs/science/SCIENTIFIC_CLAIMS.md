# IFCtoFDS — Scientific Claim Ledger

**Baseline governance SHA:** `main@cb5424f3886d8269ff8fd45b07f7b57c4ff3f67d`  
**Overall scientific/application verdict:** `INCONCLUSIVE`  
**Release verdict:** `NOT_PRODUCTION_READY`

This ledger is the fail-closed registry for scientific and verification claims. A claim that is absent from this ledger must not be asserted as accepted. A `PASS` applies only to the exact statement and validation domain written below; it does not lift downstream verification or validation levels.

## Rules

1. Allowed acceptance verdicts are only `PASS`, `FAIL`, `INCONCLUSIVE`, and `NOT_APPLICABLE`.
2. Evidence levels are `E0` through `E6`: no evidence, source rationale, software verification, numerical/solution verification, experimental validation, application validation with uncertainty, and independent reproduction/review.
3. `E0` can never support `PASS`.
4. Solver regression is not model validation. Parser acceptance is not solver verification. Mapping verification is not simulation verification.
5. Experimental/application claims cannot be raised to `PASS` without measurement uncertainty, numerical uncertainty where applicable, domain of applicability, and supporting artifacts.
6. Evidence references must point to immutable/reproducible repository or CI artifacts where possible. Existing `result_evidence.json` remains an integrity index; it does not by itself raise scientific evidence level.
7. `reviewer=PENDING_INDEPENDENT_REVIEW` is an explicit blocker for claims whose target level requires independent review.

## Claim `FDS-PARSER-001`
- **statement**: The Python Verified Core parser recognizes the reviewed FDS 6.11.1 scientific namelist subset and rejects missing required fields, unsupported fields, nonfinite values, and dangling supported references without depending on namelist order.
- **intended_use**: Parser/schema prerequisite for thermal materials, detection/suppression, instrumentation and later scientific evidence generation.
- **affected_modules**: ifc_to_fds/validation/parser.py, ifc_to_fds/validation/solver.py, parser contract tests, pinned FDS solver regression.
- **evidence_level**: E2
- **supporting_evidence**: PR #68 candidate 125d3175066a4b12e96d23b06a99801293dcf5e5; Conversion correctness #42349141483 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; Source quality and regression evidence #42349141425 PASS with 862 passed, 13 deselected and 87% coverage; solver-evidence artifact 13564483853 digest sha256:463110d3e78cb6d91c3c611232a7a06841fbcae3832929df86d96b805e2846fa. P3a re-verification on code candidate 6169b55321d6c7404d7b1a39d3633f3aef2733a9 found that FDS 6.11.1 rejects `SURF.FUEL_ID`; the default scientific parser now rejects that field, while an explicit legacy-only compatibility flag preserves historical parsing. Conversion #42380373058 and solver artifact 13577781396 (sha256:686ada474718c4261eeac039d4548c1ce75453b50cdf5a3aa042c44701861c9c) verify the corrected contract.
- **known_limitations**: This is a deliberately supported subset, not a complete FDS grammar. `allow_legacy_surf_fuel_id=True` is compatibility-only and must not be treated as FDS 6.11.1 scientific support. Parser/solver syntax acceptance does not establish numerical convergence, model validation, application validation or physical appropriateness of accepted parameter values.
- **validation_domain**: FDS 6.11.1 fields explicitly enumerated by the project parser contract and exercised by repository parser/solver fixtures.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_AND_PINNED_SOLVER_REVIEW

## Claim `GEOM-SER-001`
- **statement**: Supported JS conversion paths count only nondegenerate GEOM triangles consistently across serializer, strategy summary, and parsed scene.
- **intended_use**: Software regression and conversion accounting.
- **affected_modules**: `js/fds/fds-exporter.js`, `js/fds/fds-geometry-adapter.js`, `scripts/test-ifc-conversion.js`.
- **evidence_level**: E2
- **supporting_evidence**: PR #66; CI Conversion #42346485876; main Conversion #42347061448; synthetic valid-plus-degenerate and all-degenerate regression cases.
- **known_limitations**: Does not establish IFC geometry fidelity, volume conservation, numerical accuracy, or CFD validity.
- **validation_domain**: Current JS exporter semantics and repository IFC regression fixtures.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_AND_DIFF_REVIEW

## Claim `SOLVER-REG-001`
- **statement**: The pinned FDS 6.11.1 executable accepts and completes the repository solver regression fixtures under the current solver contract.
- **intended_use**: Solver integration regression only.
- **affected_modules**: `scripts/install-fds.py`, solver-marked tests, FDS emission and validation paths.
- **evidence_level**: E2
- **supporting_evidence**: PR #66 solver job in Conversion #42346485876 reported 7 passed and 853 deselected; main Conversion #42347061448 also passed.
- **known_limitations**: Does not prove mesh independence, predictive accuracy, EV fire model validity, or application safety.
- **validation_domain**: Repository solver fixtures with pinned FDS 6.11.1.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_AND_DIFF_REVIEW

## Claim `EVID-INT-001`
- **statement**: New convert/scenario job evidence indexes detect missing or modified declared persisted artifacts in the supported integrity-check paths.
- **intended_use**: Tamper-evidence and cross-file consistency for persisted job outputs.
- **affected_modules**: `ifc_to_fds/adapters/jobs/evidence_index.py`, job repository and acceptance-audit tests.
- **evidence_level**: E2
- **supporting_evidence**: `tests/test_job_evidence_index.py`, acceptance audit regressions, main Quality #42347061455.
- **known_limitations**: Not a digital signature, not adversarial tamper resistance, and not evidence of physical/scientific validity.
- **validation_domain**: Declared convert/scenario artifacts handled by the current evidence-index contract.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_AND_DIFF_REVIEW

## Claim `GEO-PREFLIGHT-001`
- **statement**: When source-topology fail-fast is enabled, an in-scope physical source mesh with confirmed self-intersection is rejected before dependent Air Path, Openings and Solver gates execute; an uncertain self-intersection remains INCONCLUSIVE; structured witness evidence is preserved without repairing or substituting source geometry.
- **intended_use**: Software verification of fail-closed geometry gate ordering and diagnostic traceability before downstream enclosure/opening/solver checks.
- **affected_modules**: `ifc_to_fds/validation/preflight.py`, `ifc_to_fds/validation/engine.py`, `ifc_to_fds/validation/runner.py`, Geometry checker and source-topology regression tests.
- **evidence_level**: E2
- **supporting_evidence**: PR #73 code candidate `a8076880c12ddf8ec382f3fc270e190b0457ab05`; Source quality #42385398407 PASS with 894 passed, 14 deselected and 87% coverage, artifact 13579038618 digest sha256:acaaf526ce12501ce136457183112f80329cadd122411e49327277e78721819e; Conversion #42385398466 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; solver artifact 13579825786 digest sha256:8b20558c44bc7aaa28f8e2673bafdfce25949d074ccbd2fa9f8f4d39a9874a67. Regression CI first exposed and then verified repair of FZK geometry-preservation parity and Duplex finding-count compatibility without changing golden expectations.
- **known_limitations**: This claim does not repair invalid IFC geometry, authorize bounding-box fallback, prove enclosure airtightness, establish mesh adequacy, verify FDS numerical accuracy, or validate any fire-physics model. Explicit reviewed dispositions remain required when invalid source elements are intentionally excluded or reclassified.
- **validation_domain**: Repository source-topology fixtures, FZK/Duplex behavior-parity fixtures and the current fail-fast/full-diagnostics audit contracts.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_AND_DIFF_REVIEW

## Claim `EV-GEO-P3A-001`
- **statement**: For the scoped axis-aligned P3a contract, `PARAMETRIC` vehicle geometry preserves explicit floor reference and positive underbody clearance, while reviewed `IFC_BOUND` geometry preserves canonical vehicle identity and verified OBST bounds without duplicating the base body; reviewed battery bounds are traceable and contained within the vehicle envelope; both scientific modes emit an underbody burner accepted by pinned FDS 6.11.1.
- **intended_use**: Software/solver-integration verification of the vehicle identity and ground-clearance prerequisite before local MeshPlan and EV physics work.
- **affected_modules**: `ifc_to_fds/fire/vehicle_geometry_models.py`, `ifc_to_fds/fire/vehicle_geometry.py`, `ifc_to_fds/fire/scenario_emitter.py`, scenario composer/runner evidence path, mapping policy, parser contract and P3a regression tests.
- **evidence_level**: E2
- **supporting_evidence**: PR #69 code candidate `6169b55321d6c7404d7b1a39d3633f3aef2733a9`; Source quality #42380373024 PASS with 879 passed, 14 deselected and 87% coverage, artifact 13577831468 digest sha256:37b0be1cc4c529a94cb5eaf2b96ff09727798c654598d3651c099b114eec23a9; Conversion #42380373058 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; solver job reports 9 passed, 884 deselected; solver artifact 13577781396 digest sha256:686ada474718c4261eeac039d4548c1ce75453b50cdf5a3aa042c44701861c9c. The solver fixture uses dz=0.05 m, giving 3 cells across the 0.15 m parametric clearance and 4 cells across the 0.20 m IFC-bound clearance.
- **known_limitations**: This claim does not cover rotated/non-axis-aligned vehicle orientation, automatic native IFC vehicle classification, vehicle-to-wall/column collision acceptance, jet outlets, GEOM-bound vehicles, post-snap clearance in a production MeshPlan, grid sensitivity, thermal materials, EV reaction/species validity, numerical verification or experimental/application validation. FDS emits warnings that the current REAC should use SPEC-defined fuel chemistry and that the generated OFFGAS species is undefined in the built-in table; those are retained as P6 physics limitations and prevent upgrading this scoped geometry evidence into a physics claim.
- **validation_domain**: Axis-aligned PARAMETRIC vehicles and reviewed IFC_BOUND passive-obstacle source bounds exercised by repository P3a fixtures, with exact pre-snap bounding-box arithmetic and pinned FDS 6.11.1 solver acceptance only.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_PINNED_SOLVER_AND_DIFF_REVIEW

## Claim `EV-GEO-P3B-001`
- **statement**: For the scoped P3b contract, scientific `PARAMETRIC` and `IFC_BOUND` vehicles are separated from every verified base `OBST` by a positive AABB clearance greater than `1e-4 m`; disjoint base `GEOM` AABBs are accepted as proven-separated, while touching/overlapping `GEOM` AABBs fail closed as `INCONCLUSIVE`; own IFC-bound vehicle/battery sources are excluded explicitly and all other emitting base entities remain checked.
- **intended_use**: Software-level collision/contact prevention between supported axis-aligned EV scenario geometry and verified base geometry before orientation, exact GEOM collision and local-mesh work.
- **affected_modules**: `ifc_to_fds/fire/vehicle_collision.py`, `ifc_to_fds/fire/scenario_emitter.py`, scenario worker evidence path and P3b regression/E2E tests.
- **evidence_level**: E2
- **supporting_evidence**: PR #71 code candidate `6ad904c7b5fb975968e856fa8bbc686b4b6b4d85`; Source quality #42382470834 PASS with 889 passed, 14 deselected and 87% coverage, artifact 13578780011 digest sha256:43ea31cc163100cd89c61a7b711cac5ca597b84c4cdde44005871f62829c71f1; Conversion #42382470941 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; solver job reports 9 passed, 894 deselected; solver artifact 13577534013 digest sha256:b1575008ebed1e2d3694e25b50dcf3cc1e930a839ba6d45013a614702f5eb6b4. Worker E2E converts a real IFC perimeter base and persists machine-readable `vehicle_collision_assessments`.
- **known_limitations**: AABB overlap/touch with `GEOM` is rejected rather than resolved by exact triangle-mesh intersection; rotated/non-axis-aligned vehicle fidelity, native automatic IFC vehicle classification, post-snap clearance, local MeshPlan/grid sensitivity, jet outlets, EV physics and application validation remain outside P3b.
- **validation_domain**: Axis-aligned P3a vehicle bodies checked against verified base OBST/GEOM representation bounds available in MappingPlan; positive AABB separation only.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_PINNED_SOLVER_AND_DIFF_REVIEW

## Claim `EV-GEO-001`
- **statement**: EV scenario geometry preserves IFC vehicle identity, battery location, orientation, and ground clearance through IFC-to-FDS emission.
- **intended_use**: EV underbody fire geometry and local-mesh scientific analysis.
- **affected_modules**: `ifc_to_fds/fire/scenario_request.py`, `ifc_to_fds/fire/scenario_emitter.py`, vehicle geometry/collision domain, mapping policy and future P3c orientation/exact-GEOM work.
- **evidence_level**: E2
- **supporting_evidence**: Scoped claims `EV-GEO-P3A-001` and `EV-GEO-P3B-001` verify explicit source binding, axis-aligned body/battery bounds, positive pre-snap ground clearance and fail-closed separation from verified base geometry for supported cases. The full statement still lacks rotated orientation preservation, exact collision resolution for overlapping GEOM AABBs, jet-outlet geometry, production post-snap/local-mesh clearance evidence and real IFC application evidence.
- **known_limitations**: Automatic native IFC vehicle classification, rotated/non-axis-aligned orientation fidelity, exact GEOM collision when AABBs overlap, jet outlets, post-snap clearance metrics, local MeshPlan sensitivity and application-specific geometry evidence remain incomplete.
- **validation_domain**: Full P3 vehicle-geometry claim remains broader than the scoped P3a fixtures and is therefore not accepted.
- **status**: FAIL
- **reviewer**: PENDING_INDEPENDENT_REVIEW

## Claim `MESH-LOCAL-001`
- **statement**: The simulation uses a reviewed local/refined MeshPlan that resolves the EV source, underbody clearance, battery thickness, and near-field plume with documented sensitivity.
- **intended_use**: Numerical/solution verification for EV fire scenarios.
- **affected_modules**: Future `MeshPlan`, mesh checker, scenario evidence and metrics.
- **evidence_level**: E0
- **supporting_evidence**: No accepted MeshPlan/local-refinement evidence package is registered in this ledger.
- **known_limitations**: D-star over dx alone is not an acceptance rule; coarse/medium/fine sensitivity and critical-gap cell counts are missing.
- **validation_domain**: EV basement/garage simulation cases.
- **status**: INCONCLUSIVE
- **reviewer**: PENDING_INDEPENDENT_REVIEW

## Claim `MATL-THERM-001`
- **statement**: IFC material associations and ordered layers are mapped to FDS thermal MATL/SURF records with explicit SI units and provenance.
- **intended_use**: Heat-transfer boundary conditions for scientific simulation.
- **affected_modules**: Future IFC material extraction, material library, surface mapping and material checker.
- **evidence_level**: E0
- **supporting_evidence**: No accepted thermal-material mapping evidence package is registered in this ledger.
- **known_limitations**: Missing or assumed conductivity, density, specific heat, thickness, or temperature dependence must not silently receive PASS.
- **validation_domain**: Research/scientific profile only after material provenance is supplied.
- **status**: INCONCLUSIVE
- **reviewer**: PENDING_INDEPENDENT_REVIEW

## Claim `EV-PHYS-001`
- **statement**: EV HRR, reaction, radiative fraction, CO/soot/HF yields, and jet distribution predict the intended EV fire phenomena within a stated application domain.
- **intended_use**: Quantitative EV fire CFD and downstream tenability assessment.
- **affected_modules**: `ifc_to_fds/fire/ev_library.py`, `ifc_to_fds/fire/scenario_emitter.py`, future EV physics v2 modules.
- **evidence_level**: E1
- **supporting_evidence**: Versioned EV preset records carry citations/ranges/confidence, but no accepted experimental comparison matrix is linked here.
- **known_limitations**: Current emitter uses simplified reaction/source assumptions; quantitative HF remains explicitly unsupported; experimental uncertainty and application validation are missing.
- **validation_domain**: Not yet established for scientific acceptance.
- **status**: INCONCLUSIVE
- **reviewer**: PENDING_INDEPENDENT_REVIEW

## Claim `HVAC-MAP-001`
- **statement**: Supported HVAC network fixtures preserve declared connectivity and pass the current software-level HVAC mapping/validation contract.
- **intended_use**: Software verification of supported HVAC mapping semantics.
- **affected_modules**: `ifc_to_fds/domain/mep/hvac.py`, HVAC validators/checkers, `tests/test_hvac_network.py`.
- **evidence_level**: E2
- **supporting_evidence**: `tests/test_hvac_network.py`, `docs/evidence/hvac-network-v1/`, current full CI.
- **known_limitations**: Does not validate fan curves, smoke-control performance, control sequences, mass-balance accuracy in a real building, or application safety.
- **validation_domain**: Supported repository HVAC fixtures and declared topology contract.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_AND_DIFF_REVIEW

## Claim `DET-SUP-001`
- **statement**: IFC detection and suppression semantics are mapped to solver-accepted DEVC/PROP/PART/CTRL records with traceable activation and flow parameters.
- **intended_use**: Detection/sprinkler response simulation.
- **affected_modules**: Future detector/sprinkler adapters, parser contract and solver tests.
- **evidence_level**: E0
- **supporting_evidence**: No accepted end-to-end detection/suppression mapping evidence package is registered in this ledger.
- **known_limitations**: Parser support or isolated device records cannot substitute for reference integrity and solver execution.
- **validation_domain**: Not yet established.
- **status**: INCONCLUSIVE
- **reviewer**: PENDING_INDEPENDENT_REVIEW

## Claim `ASET-001`
- **statement**: ASET-driving quantities are instrumented at defined locations/heights and first threshold crossings are computed using cited, scenario-specific criteria.
- **intended_use**: Performance-based fire safety tenability assessment.
- **affected_modules**: Future instrumentation, tenability extraction, evidence metrics.
- **evidence_level**: E0
- **supporting_evidence**: No accepted instrumentation/ASET evidence package is registered in this ledger.
- **known_limitations**: RSET remains external; no threshold is treated as a universal regulatory truth; fire-model validation is prerequisite to application acceptance.
- **validation_domain**: Not yet established.
- **status**: INCONCLUSIVE
- **reviewer**: PENDING_INDEPENDENT_REVIEW

## Claim `B1B2-APP-001`
- **statement**: The B1/B2 reference case is scientifically acceptable for its declared application domain with geometry, physics, mesh sensitivity, uncertainty, solver evidence, and independent review.
- **intended_use**: Final research/application acceptance case.
- **affected_modules**: `reference-cases/basement-b1-b2/`, scientific metrics and validation evidence.
- **evidence_level**: E1
- **supporting_evidence**: Reference-case files and acceptance profile exist, while the approval bundle remains draft/incomplete for final scientific acceptance.
- **known_limitations**: Experimental/application comparison, uncertainty, approved provenance, and independent review are not complete.
- **validation_domain**: B1/B2 case only after explicit approval and evidence completion.
- **status**: INCONCLUSIVE
- **reviewer**: PENDING_INDEPENDENT_REVIEW
