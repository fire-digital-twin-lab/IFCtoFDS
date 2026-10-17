# Verified mapping functional correction

Base: `codex/post-refactor-correctness`, `c7462d1b88935fc50390786e2ce49fbc3a460ab1`.
Work branch: `codex/verified-mapping-correctness`.

## Stage A: dependency and truth boundaries

```mermaid
flowchart TD
  IFC[Immutable IFC bytes + SHA-256] --> INV[Inventory, placements, spatial ancestry]
  INV --> MEP[Explicit systems, ports and connections]
  INV --> SRC[IfcOpenShell source geometry]
  SRC --> SCOPE[Geometry + building/storey selection]
  MEP --> SCOPE
  DOMAIN[Declared fixed simulation domain] --> POLICY[Mapping policy]
  SCOPE --> POLICY
  REVIEW[Reviewed decisions] --> POLICY
  POLICY --> PLAN[Approved MappingPlan snapshot]
  PLAN --> REP[Separate representation geometry]
  SRC --> REP
  REP --> FDS[Serialized FDS + manifest]
  SRC --> PKG[Saved full source geometry package]
  IFC --> AUDIT[Independent source re-read]
  FDS --> AUDIT
  PKG --> AUDIT
  AUDIT --> GATES[Geometry, openings, MEP, scope, provenance gates]
  GOLDEN[Content-bound approved reference, if required] --> GATES
  SOLVER[Pinned solver and effective geometry, when required] --> GATES
  GATES --> REPORT[Separate mapping / simulation / research verdicts]
```

The converter's geometry cache is never an independent audit reference. Counts
from older revisions are observations, not acceptance criteria. Unsupported
source geometry, uncertainty and pending boundary treatment block acceptance.

## Execution record

- A: inspected policy/scope/boundary/serializer, geometry, MEP, validation and use cases.
- B–J: tracked in focused implementation commits and the final evidence report.
- Private IFC evidence is kept outside Git under `.local-reference-cases/functional-correctness/`.
- No golden approval, scenario physics, generic GEOM clipping or automatic merge is included.
