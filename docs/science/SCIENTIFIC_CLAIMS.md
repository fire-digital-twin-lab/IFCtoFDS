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

## Claim `EV-GEO-P3C-001`
- **statement**: For the scoped P3c axis-aligned OBST contract, reviewed `IFC_BOUND` vehicle source identity and CONFIRMED placement provenance survive verified-base reload; accepted orientation requires a finite proper rigid quarter-turn ObjectPlacement with no tilt/mapped-item transforms and an independent cross-check that the placement X axis agrees with the major horizontal axis of the verified OBST. Ambiguous square footprints and ObjectPlacement/body-axis mismatch, including real IFC `IfcSweptAreaSolid.Position` rotation, fail closed.
- **intended_use**: Software-level orientation/provenance verification for reviewed IFC-bound EV obstacle geometry before arbitrary GEOM orientation, directional outlets and local-mesh work.
- **affected_modules**: `ifc_to_fds/domain/mapping/model.py`, `ifc_to_fds/domain/mapping/plan.py`, `ifc_to_fds/mapping/plan_validation.py`, `ifc_to_fds/application/services/scenario_base.py`, `ifc_to_fds/fire/vehicle_geometry.py`, vehicle geometry evidence and P3c regression tests.
- **evidence_level**: E2
- **supporting_evidence**: PR #72 code candidate `7866d0f341779cef2f2c5e44d5e5c5f948d9b3d6`; Source quality #42389022580 PASS with 912 passed, 14 deselected, 113 warnings and 87% coverage; source-quality artifact `13580833047` digest sha256:2a1842350cfa6e3417a4c03e47dfca80c1f7c442d902d0730fee9fa6e6c43e42; Conversion #42389022590 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; solver artifact `13581090420` digest sha256:5339b3cd20fc60d6f4a0de2a7a6b4d660af67c9b342559f46e989afb8f743e83. Regression includes a real IFC whose `IfcSweptAreaSolid.Position` rotates the body relative to ObjectPlacement and verifies that the orientation claim is rejected. Contract note: `docs/science/P3C_ORIENTATION_PROVENANCE_CONTRACT.md`.
- **known_limitations**: Verified OBST bounds establish the longitudinal axis only modulo 180° and do not prove front/rear heading. This claim does not authorize directional jet outlets, asymmetric front/rear source placement, arbitrary rotated GEOM vehicles, general representation-item or mapped-item composition, automatic native `IfcVehicle` classification, exact GEOM collision, post-snap/local MeshPlan clearance, grid sensitivity, EV physics, numerical verification, experimental validation or application validation.
- **validation_domain**: Reviewed `IFC_BOUND` vehicle sources represented as verified axis-aligned rectangular OBSTs with a distinct major horizontal axis and CONFIRMED quarter-turn placement provenance.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_PINNED_SOLVER_IFC_STANDARD_AND_DIFF_REVIEW

## Claim `EV-GEO-P3D-001`
- **statement**: For the current scientific vehicle contract whose resolved body is an axis-aligned AABB, collision/clearance against a MAPPING_VERIFIED base can be resolved when base GEOM AABBs overlap or touch by reconstructing the exact emitted GEOM from the sealed FDS artifact, validating its manifest provenance, and testing every relevant triangle against an outward-expanded 1e-4 m vehicle box with an exact-rational 13-axis triangle/AABB SAT plus reviewed solid-boolean containment. Missing, mismatched, invalid, self-intersecting or numerically unavailable exact evidence fails closed.
- **intended_use**: Software-level vehicle-to-building collision/clearance verification for current PARAMETRIC and IFC_BOUND axis-aligned vehicle bodies before local/post-snap MeshPlan work.
- **affected_modules**: `ifc_to_fds/application/services/scenario_base.py`, `ifc_to_fds/fire/base_geometry.py`, `ifc_to_fds/fire/vehicle_collision.py`, `ifc_to_fds/fire/scenario_emitter.py`, `ifc_to_fds/geometry/triangle_box.py`, scenario worker integration and P3d regression tests.
- **evidence_level**: E2
- **supporting_evidence**: PR #74 code candidate `834bad73e218a171329293fe2567c9e3f13c1212`; Source quality #42391766635 PASS with 924 passed, 14 deselected, 117 warnings and 87% coverage; source-quality artifact `13581603383` digest sha256:ccde0618a8057504e53f797abd4255755c3d053572593ff33b7d50c01e148c94; Conversion #42391766582 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; solver artifact `13582350222` digest sha256:c67a206755b4cc767d99d2619cfe06d3d73fc5247a92aa47205dbd1905d7a013; browser artifact `13581782426` digest sha256:be40c96b6f513790603068c5df12b34174769bb8f920faf2a21fe4a50e0a1b07. Regression includes exact binary64 contact/separation predicates, overlapping AABBs with a separated tetrahedron, sub-tolerance clearance, full containment, provenance failures and a worker E2E path that converts/seals/reloads a real all-GEOM base. Contract note: `docs/science/P3D_EXACT_GEOM_COLLISION_CONTRACT.md`.
- **known_limitations**: The current clearance envelope is an axis-expanded conservative box, not an exact Euclidean offset surface; FAIL can therefore be conservative near diagonal corners while PASS remains sound for >1e-4 m Euclidean separation. The claim does not cover arbitrary rotated vehicle OBB/GEOM bodies, front/rear heading, local/post-snap MeshPlan clearance, grid sensitivity, jet/outlet geometry, EV fire physics, numerical verification, experimental validation or application validation.
- **validation_domain**: Current axis-aligned PARAMETRIC/IFC_BOUND resolved vehicle body AABBs checked against sealed emitted OBST/GEOM geometry from MAPPING_VERIFIED base artifacts.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_PINNED_SOLVER_PUBLISHED_SAT_AND_DIFF_REVIEW

## Claim `EV-GEO-001`
- **statement**: EV scenario geometry preserves IFC vehicle identity, battery location, orientation, and ground clearance through IFC-to-FDS emission.
- **intended_use**: EV underbody fire geometry and local-mesh scientific analysis.
- **affected_modules**: `ifc_to_fds/fire/scenario_request.py`, `ifc_to_fds/fire/scenario_emitter.py`, vehicle geometry/collision domain, mapping policy and future local-mesh/jet geometry work.
- **evidence_level**: E2
- **supporting_evidence**: Scoped claims `EV-GEO-P3A-001`, `EV-GEO-P3B-001`, `EV-GEO-P3C-001` and `EV-GEO-P3D-001` verify explicit source binding, axis-aligned body/battery bounds, positive pre-snap ground clearance, longitudinal-axis orientation/provenance for reviewed quarter-turn IFC-bound OBSTs, and fail-closed collision/clearance against sealed emitted OBST/GEOM for the current axis-aligned body contract. The full statement still lacks arbitrary/non-axis-aligned vehicle GEOM orientation, directed front/rear heading, jet-outlet geometry, production post-snap/local-mesh clearance evidence, automatic native IFC vehicle classification and real IFC application evidence.
- **known_limitations**: Automatic native IFC vehicle classification, arbitrary/non-axis-aligned vehicle GEOM/OBB orientation fidelity, front/rear directed heading, jet outlets, post-snap clearance metrics, local MeshPlan sensitivity and application-specific geometry evidence remain incomplete. P3d collision evidence is scoped to the current axis-aligned vehicle body and a conservative axis-expanded 1e-4 m envelope; it is not a general exact-Euclidean clearance proof.
- **validation_domain**: Full P3 vehicle-geometry claim remains broader than the scoped P3a fixtures and is therefore not accepted.
- **status**: FAIL
- **reviewer**: PENDING_INDEPENDENT_REVIEW

## Claim `MESH-INDICATOR-P4A-001`
- **statement**: The mesh checker reports D*/dx as a plume-resolution indicator without treating the historical 4–16 subset as a universal PASS/FAIL range, reports available EV ground-clearance/battery cell counts without inventing acceptance thresholds, records HRR/cell-size provenance, and preserves pinned-solver integration evidence separately from mesh scientific adequacy.
- **intended_use**: Software-level prerequisite for a later typed Local MeshPlan and coarse/medium/fine solution-verification workflow.
- **affected_modules**: `ifc_to_fds/validation/checkers/mesh_resolution.py`, `ifc_to_fds/validation/checkers/solver.py`, `ifc_to_fds/validation/engine.py`, mesh/scenario/API regression tests.
- **evidence_level**: E2
- **supporting_evidence**: PR #75 code candidate `ffe9d7ed519028a68ce8aa35ecf5530fcf8edfcd`; Source quality #42403923771 PASS with 926 passed, 14 deselected, 117 warnings and 87% coverage; artifact 13587020449 digest sha256:a8d5add592ecb6431cd98c31effda642e2ab80ecac7c147f6b6f410f1ae29aab. Conversion #42403923594 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; solver artifact 13586344048 digest sha256:d27dea30722b310a72cae6d3ed752bb134b86378aea00fc46899b4f9a3463f69; browser artifact 13586059568 digest sha256:ac78e95294343660e4ed4d25cd8954bffe943560a19f97fa993e4ace1adfc18e. Technical note: `docs/science/P4A_MESH_ADEQUACY_INDICATOR_CONTRACT.md`.
- **known_limitations**: At the P4a baseline the checker did not resolve a source-local mesh and therefore labeled parsed-FDS spacing as global maximum/not source-local. Scoped P4b1 later adds fail-closed source-local lookup and a typed Local MeshPlan, but P4a itself still provides no grid-sensitivity series, numerical uncertainty or application validation. A solver PASS is integration evidence only and does not upgrade mesh adequacy.
- **validation_domain**: Current repository fire-source fixtures, scenario/API jobs and both validation orchestration paths; indicator/provenance semantics only.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_PINNED_SOLVER_AND_DIFF_REVIEW

## Claim `MESH-LOCAL-P4B1-001`
- **statement**: For the scoped P4b1 contract, a scenario may replace the verified base uniform MESH layout with a typed coarse-lattice-aligned Local MeshPlan whose coarse shell and one refined source region cover the same simulation domain without interior overlap; requested-to-effective boundary expansion is explicit, burner-to-mesh locality is fail-closed, local spacing/critical EV geometry ratios are persisted, and the regression layout completes a real pinned FDS 6.11.1 timestep run.
- **intended_use**: Software/solver-integration prerequisite for P4c coarse/medium/fine solution verification around supported scientific EV sources.
- **affected_modules**: `ifc_to_fds/fire/mesh_plan*.py`, `scenario_request.py`, `scenario_composer.py`, scenario worker evidence path, `MeshResolutionChecker`, Local MeshPlan/worker/solver regression tests.
- **evidence_level**: E2
- **supporting_evidence**: PR #76 code candidate `74d731b98c7e40d96bb55ad78f55eea8cece0a1e`; Source quality #42448081967 PASS with 936 passed, 15 deselected, 121 warnings and 87% coverage; artifact 13604293336 digest sha256:002e23b1c97629b8319e321b23935782f2d5b7581e7580c221da062fdbc8041a. Conversion #42448077861 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; solver suite reports 10 passed, 941 deselected; solver artifact 13603679195 digest sha256:42cb18b79783a00de43fa1c0f95da1d34fd49ffaf4b60539e8ade5e296adf7ff; browser artifact 13604173674 digest sha256:cccad28a042cddd4e27447b16ad70efe30ca752795f53878c269d9268f7639b6. Acceptance review additionally verifies fail-closed full-burner-extent locality: centroid-in-local but extent-spanning-interface must not receive local dx. Solver regression uses `T_END=0.1 s`, requires `completed successfully`, and persists JSON plus stdout/stderr logs/checksums. Technical note: `docs/science/P4B_LOCAL_MESH_PLAN_CONTRACT.md`.
- **known_limitations**: One explicit source-local region only; local refined region is one mesh with a current 500,000-cell implementation guard; requested boundaries may expand outward on the verified coarse lattice to avoid one-cell 3D meshes and every adjustment is recorded. This claim does not establish grid convergence, mesh independence, numerical uncertainty, application-specific adequacy or any fire-physics validity. D*/dx and cells-across-gap metrics remain indicators, not universal acceptance thresholds.
- **validation_domain**: Current axis-aligned scientific vehicle/burner fixtures, a verified uniform coarse base lattice, one explicit local refinement patch with integer ratio, full-burner-extent locality checks, WorkerRunner scenario persistence and the pinned FDS 6.11.1 regression layout.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_PINNED_SOLVER_AND_DIFF_REVIEW

## Claim `MESH-SENS-P4C1-001`
- **statement**: The scoped P4c1 software contract resolves exactly three comparable COARSE/MEDIUM/FINE Local MeshPlans over one invariant pre-mesh scenario, enforces strictly increasing refinement ratios and decreasing local spacing, requires observable unit/location/time-window provenance, rejects non-mesh scenario or observable-metadata drift, and reports pairwise grid changes/trends without inventing a convergence threshold or numerical-uncertainty claim.
- **intended_use**: Software/comparability prerequisite for executed P4c2 FDS grid-sensitivity studies and later reviewed solution-verification analysis.
- **affected_modules**: `ifc_to_fds/fire/grid_sensitivity*.py`, public fire facade and `tests/test_grid_sensitivity.py`.
- **evidence_level**: E2
- **supporting_evidence**: PR #77 code candidate `f28f8846c17dfc4952f3862d6ef4dabf6c0a7cd2`; Source quality #42450794968 PASS with 945 passed, 15 deselected, 121 warnings and 87% coverage; artifact 13605856905 digest sha256:9553d7784611eb54ce27d09753da6c4e323424fa16574090b857a47f87aadeab. Conversion #42450791576 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; solver suite reports 10 passed, 950 deselected; solver artifact 13605681774 digest sha256:c9bca00d25733a1bcdf622becdde33ea1790f685c730395d123b9d2a5a896f33; browser artifact 13605426706 digest sha256:51d583523d47c4c70f4dd9301e98170c8c5412c655a7ec39ef33e1db4818d18e. Technical note: `docs/science/P4C1_GRID_SENSITIVITY_CONTRACT.md`.
- **known_limitations**: P4c1 does not execute the three FDS cases as a study package, does not parse solver output/DEVC CSV, does not define a reviewed convergence acceptance policy, does not estimate observed order/GCI/Richardson/numerical uncertainty, and does not demonstrate application-specific mesh independence. Its result status is intentionally INCONCLUSIVE.
- **validation_domain**: Current P4b-compatible Local MeshPlan fixtures and software-level observable/comparability contracts only.
- **status**: PASS
- **reviewer**: REPOSITORY_CI_AND_DIFF_REVIEW

## Claim `MESH-LOCAL-001`
- **statement**: The simulation uses a reviewed local/refined MeshPlan that resolves the EV source, underbody clearance, battery thickness, and near-field plume with documented sensitivity.
- **intended_use**: Numerical/solution verification for EV fire scenarios.
- **affected_modules**: Future `MeshPlan`, mesh checker, scenario evidence and metrics.
- **evidence_level**: E0
- **supporting_evidence**: Scoped claims `MESH-INDICATOR-P4A-001`, `MESH-LOCAL-P4B1-001` and `MESH-SENS-P4C1-001` verify indicator semantics, a typed non-overlapping Local MeshPlan, fail-closed source-local spacing, critical EV geometry ratios, pinned-solver acceptance, and a software-level three-grid comparability/observable contract. They do not yet provide an executed coarse/medium/fine output study or a reviewed convergence/uncertainty decision.
- **known_limitations**: P4c2 still needs to execute three comparable FDS cases, ingest real solver observables, and demonstrate the behavior of application-relevant quantities. Reviewed convergence criteria, numerical uncertainty and application-specific mesh adequacy are still missing; current evidence does not prove grid independence.
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
