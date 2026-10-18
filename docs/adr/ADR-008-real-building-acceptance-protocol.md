# ADR-008: Real-Building Model Acceptance Protocol and Research Verification Governance

## Status
Accepted

## Context
In previous revisions of the IFCtoFDS project and research case studies (such as the two-level basement fire simulation case study `21_BASEMENT_CASE_STUDY.md` involving B1/B2 parking and mechanical rooms), candidate reference cases risk being marked as verified or ground-truth without independent physical verification, licensed drawings, or measured fire protection equipment parameters.

Computational conversion tools cannot infer physical boundary conditions, mechanical ventilation rates, or sensor actuation curves without licensed engineering documentation. Treating an automated conversion of a proprietary or unverified IFC file as an approved reference baseline introduces non-reproducible biases and violates scientific integrity.

## Decision
We establish a formal, enforceable Four-Clause Governance Protocol for real-building IFC model acceptance:

### Clause 1: Default Draft Status for Real-Building Candidates
Any automated conversion or golden candidate bundle generated from an unverified real-building model MUST produce an `approval.json` initialized with:
```json
{
  "status": "DRAFT",
  "origin": "AUTOMATIC_CANDIDATE_NOT_GROUND_TRUTH"
}
```
Software algorithms are strictly prohibited from automatically elevating an unverified building candidate to `APPROVED`.

### Clause 2: Strict Prohibition of Inferred Physics
Software MUST NOT invent physical parameters:
- Ventilation fan flow rates ($m^3/s$) and pressure curves
- CO sensor alarm thresholds ($ppm$) and heat detector activation temperatures ($^\circ C$)
- Sprinkler droplet RTI ($m^{1/2}s^{1/2}$) and discharge density
- Fire HRR curves ($kW$) and fuel soot yields

Any unconfigured MEP operational status MUST remain `NOT_CONFIGURED` or `REVIEW_REQUIRED`, with elements routed into `review-queue.json` awaiting human engineer input.

### Clause 3: Boundary Verification for Sub-Storey Trimming
When spatial scoping isolates basement levels (e.g. B1/B2) while omitting above-ground storeys, sidewalks, or ramps:
- Structural elements crossing the spatial bounding plane must carry explicit `BOUNDARY_RETAINED` policy decisions with documented geometric clipping evidence.
- The AirPath and boundary gates must independently certify that boundary cut-planes do not introduce artificial envelope leakage into the fire simulation domain.

### Clause 4: Promotion Criteria to APPROVED Ground Truth
Promotion of a reference case from `DRAFT` to `APPROVED` requires all of the following conditions to be certified:
1. **Source Model Authenticity**: Source IFC immutable SHA-256 digest verified against stamped construction drawings.
2. **On-Site Field Verification**: Physical survey confirming spatial dimensions, fire compartment walls, and door/window opening voids.
3. **Engineering Parameter Sign-off**: Registered Fire Protection Engineer approval recorded in `approval.json` with professional license credentials.
4. **Zero P0/P1 Gate Violations**: All 11 independent validation gates report `PASS`.
5. **Numerical Stability**: FDS smoke solver execution completes without numerical divergence or grid boundary reflections.

## Consequences
- Prevents unverified IFC models from being cited as empirical proof of software correctness.
- Guarantees strict scientific reproducible standards for research publications and academic theses.
- Ensures a clear legal and operational division between software geometric extraction and licensed engineering decision-making.
