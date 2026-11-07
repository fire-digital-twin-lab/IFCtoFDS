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
- **supporting_evidence**: PR #68 candidate 125d3175066a4b12e96d23b06a99801293dcf5e5; Conversion correctness #42349141483 PASS across Linux/Windows Python 3.10–3.13, JavaScript, browser and pinned FDS; Source quality and regression evidence #42349141425 PASS with 862 passed, 13 deselected and 87% coverage; solver-evidence artifact 13564483853 digest sha256:463110d3e78cb6d91c3c611232a7a06841fbcae3832929df86d96b805e2846fa.
- **known_limitations**: This is a deliberately supported subset, not a complete FDS grammar; parser/solver syntax acceptance does not establish numerical convergence, model validation, application validation or physical appropriateness of accepted parameter values.
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

## Claim `EV-GEO-001`
- **statement**: EV scenario geometry preserves IFC vehicle identity, battery location, orientation, and ground clearance through IFC-to-FDS emission.
- **intended_use**: EV underbody fire geometry and local-mesh scientific analysis.
- **affected_modules**: `ifc_to_fds/fire/scenario_request.py`, `ifc_to_fds/fire/scenario_emitter.py`, future vehicle geometry domain model.
- **evidence_level**: E2
- **supporting_evidence**: Current `EVSelection` lacks IFC entity binding and ground-clearance fields; current emitter constructs a parametric full-body `OBST` and places the burner `VENT` on its top surface.
- **known_limitations**: No accepted IFC_BOUND vehicle model, battery-pack primitive, post-snap clearance metric, or geometry fidelity evidence exists for this claim.
- **validation_domain**: Current EV scenario emitter at `main@cb5424f3`.
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
