# 08 — Validation Architecture

## One audit path

The only production audit is `run_independent_validation` in `ifc_to_fds/validation/engine.py`. It re-reads the
source IFC, parses the serialized FDS text and fills one `AcceptanceReport`. The verdict comes from
`AcceptanceReport.finalize()` in `ifc_to_fds/domain/validation/model.py`; there is no second evaluator.

```text
re-read IFC + parsed FDS + manifest
        │
        ├── engine: syntax, source_inventory, traceability, scope, geometry, openings,
        │           mep, representation, boundary, domain, geometry_preservation
        ├── checkers (ifc_to_fds/validation/checkers, validation/passage_resolution.py):
        │           structural_completeness, air_path, hvac, mesh_resolution, passage_resolution
        └── solver gates (validation/solver.py, validation/effective.py): solver, effective_geometry
        │
        ▼
AcceptanceReport.finalize()  →  status, mapping_status, simulation_status
```

## Gate names

`MAPPING_GATE_ORDER` / `REQUIRED_MAPPING_GATES` and `SIMULATION_GATES` in `domain/validation/model.py` are the single
source of the gate names. The engine creates the mapping gates in that order, `finalize()` and the persisted job
result contract (`adapters/jobs/result_contract.py`) both import them.

- A mapping verdict (`MAPPING_VERIFIED`) needs every required mapping gate to pass. A `NOT_APPLICABLE` gate needs
  a reason, and the non-waivable gates can never be `NOT_APPLICABLE`.
- Simulation gates only shape `simulation_status`. Their findings carry `verification_level="simulation"` so they
  never reject a correct mapping.

## Checker contract

Checkers implement `GateChecker` from `domain/validation/checkers/base.py` and return a `CheckerOutcome`
(gate result, findings, metrics). They receive a `ValidationContext` with the model, FDS text, manifest, config,
the parsed FDS and, for `air_path`, the set of elements whose emitted solids the geometry gate proved equal to
the source (`exact_elements`).
