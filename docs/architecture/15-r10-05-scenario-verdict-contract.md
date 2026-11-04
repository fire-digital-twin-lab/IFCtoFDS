# R10-05 — Fail-closed EV scenario verdict / Không tự suy diễn nghiệm thu mô phỏng

**Base:** R10-04 PR #25. R10-05 is a stacked change, not yet on main.

## Vấn đề / Problem

The worker previously returned `verdict=PASS` when `mesh_status=PASS`
and physics did not explicitly fail. That included the case where
`physics_status=INCONCLUSIVE` and `simulation_status=NOT_RUN`.
The EV matrix panel also treated HTTP 200 and `COMPLETED` as PASS,
and accepted legacy `verdict=PASS` without scientific evidence.

This is a **status-contract bug**, not proof that FDS geometry or solver
algorithms are incorrect.

## Canonical status contract / Hợp đồng trạng thái

| Field | Meaning / Ý nghĩa |
|---|---|
| `status=COMPLETED` | The background job finished; not scientific acceptance |
| `mesh_status=PASS` | Mesh-resolution check satisfied its limited rule |
| `physics_status=INCONCLUSIVE` | Energy/physics evaluation is incomplete |
| `simulation_status=NOT_RUN` | The independent simulation-validation contract has not run |
| `verdict=FAIL` | At least one explicitly failed gate: mesh or physics |
| `verdict=INCONCLUSIVE` | No blocker found, but simulation is not independently verified |

The current worker **cannot issue PASS** as a scenario-wide scientific
acceptance verdict. Mesh and energy results remain exposed independently
so legitimate partial evidence is not lost.

The frontend normalizes any positive legacy verdict lacking independently
defined simulator-evidence proof to `INCONCLUSIVE`, while preserving
`received_verdict` and `received_simulation_status` for diagnostics.
`HTTP 200` and `COMPLETED` have no acceptance semantics.
Failures are counted as rejected; unfinished queue states are kept separate.

An actual `SIMULATION_VERIFIED` state must be defined in a **future,
reviewed schema** backed by solver/effective-geometry validation, reference
parity, uncertainty and a verifiable evidence chain. **Do not add a PASS
branch on the basis of an unvalidated string label.**

## Compatibility / Tương thích

- Existing JSON fields remain: `status`, `verdict`, `mesh_status`,
  `physics_status`, `simulation_status` and `evidence`.
- New `verdict_reason` gives a human-readable reason.
- The UI retains `received_verdict` and `received_simulation_status`
  when normalizing old/ambiguous responses.
- The existing user-visible label `Passed` is clarified to
  `Simulation verified`, which must be zero under the current workflow.
- No modifications to IFC mapping, FDS generation, actual solver execution
  or acceptance-gate numerical thresholds.

## Regression tests / Kiểm thử hồi quy

- Python `tests/test_scenario_verdict_contract.py`: nine mesh/physics
  combinations, FAIL precedence, no PASS from merely sufficient budget,
  worker contract unchanged `simulation_status=NOT_RUN`.
- Node `scripts/test-ev-scenario-panel.js`: HTTP 200 missing verdict,
  COMPLETED missing evidence, mesh-only PASS, forged/legacy PASS,
  physics FAIL, mesh FAIL, failed jobs, 500 transport errors, queued status.
- Python CI matrix, JavaScript/browser and pinned real-FDS regression are
  required before merge.

## Out of scope / Không nằm trong R10-05

This PR does not introduce an experimental-calibrated EV fire model, a
quantitative HF source, a CFD solver acceptance mechanism, or a PCCC
engineering approval. These require independent research and evidence.
