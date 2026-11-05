# Scientific verdict labels in the workbench — 05/11/2026

## Finding P1-SCI-UI

The summary status badge in `js/app-controller.js` previously grouped
`MAPPING_VERIFIED` and `SIMULATION_VERIFIED` into the same green label,
**VERIFIED**. Even though the current Python scientific pipeline does not
issue `SIMULATION_VERIFIED`, this display conflated BIM-to-FDS mapping
verification with the independent validation of CFD simulation physics.

## Correction

- `MAPPING_VERIFIED` displays **MAPPING VERIFIED**, identifying the
  precise level of proven evidence. The simulation field remains separate.
- The unsupported `SIMULATION_VERIFIED` label is **not** rendered as an
  approved green badge. It is presented as **CFD NOT VERIFIED** with an
  inconclusive visual state, pending a future scientific acceptance contract.
- The audit drawer does not echo a forged `SIMULATION_VERIFIED` status as
  accepted; displays a qualified INCONCLUSIVE marker instead.
- `INCONCLUSIVE`, `REJECTED`, and diagnostic failures keep their
  pre-existing classifications.
- No change to IFC geometry, FDS input, verification thresholds or stored
  scientific reports.

`scripts/test-verified-regressions.js` executes the actual status badge
function against a minimal DOM and checks mapping, unsupported simulation,
inconclusive, and rejected statuses. Existing JavaScript and browser CI
remain required. Additional E2E visual review with real mapping reports
and EV scenarios remains outstanding.

## Acceptance and limitations

This is **presentation-layer fail-closed protection**. It is not
independent physical verification or source evidence authentication.
The Python scientific contract review is tracked separately in PR #49.
G09/G10 remain INCONCLUSIVE until independent reference measurements,
solver convergence, uncertainty, validation of field quantities and
expert approval are documented. Release remains NOT_PRODUCTION_READY.
