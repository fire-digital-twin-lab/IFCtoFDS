# IFCtoFDS — English Change Notes

This file records the bilingual R10 refactor changes. Historical release
entries remain in the canonical [CHANGELOG.md](CHANGELOG.md).

## [Unreleased] — R10-01 (2026-11-04)

### Added
- Language-neutral diagnostic events with schema 1.0 and stable `IFCFDS.*` codes.
- English and Vietnamese catalogs with placeholder parity tests.
- Per-job canonical `events.jsonl`, plus `events.en.log` and `events.vi.log`.
- Recovery helper to regenerate both human-readable logs from the canonical stream.
- Worker failure events with error type and stage, without copying sensitive stack traces.
- Regression tests for localization, legacy progress schema, and failure propagation.

### Compatibility and limitations
- The existing `progress.json`, `diagnostics.json`, JSON API, acceptance
  statuses, and IFC-to-FDS algorithms are unchanged.
- Derived language logs are operational sidecars, not certified audit evidence.
- Frontend UI, other API errors, and solver logs are not fully localized yet.

[Tiếng Việt](CHANGELOG.vi.md) · [Technical guide](docs/en/observability.md)

## [Unreleased] — R10-03 (2026-11-04)

### Refactored
- Added a conversion workspace port and local filesystem factory to own draft FDS, MappingPlan, manifest, inventory and audit-state persistence.
- Moved portable inventory projection out of `ConvertVerifiedUseCase`.
- Kept on-disk FDS re-read and independent audit as mandatory steps; `NOT_RUN` is the pre-audit checkpoint state.
- Preserved the legacy constructor through a clearly separated transitional bridge.

### Verification
- Added checkpoint state, exact draft format, fail-closed audit sealing, container wiring, and no-direct-I/O regression tests.
- Original frozen baselines A–F and FDS solver regression remain required for merge.

## [Unreleased] — R10-04 (2026-11-04)

### Refactored
- Extracted post-engine source/package/provenance and placement checks from `AuditConversionUseCase` into `audit_integrity.py` without changing gate decisions.
- Extracted saved-MEP-graph comparison and coverage aggregation into `audit_mep_coverage.py`; the independent IFC re-read remains mandatory.
- Added a fail-closed report parity comparator for engine/runner evaluations; this does **not** replace the authoritative engine or run extra solver jobs.
- Added tests for preflight NOT_RUN, missing MEP graph, mismatching graph, validation gate/evidence/verdict mutations and the existing audit sequencing.

### Safety
- No IFC extraction, FDS generation, scientific thresholds, solver or independent audit replacement.
- Migration to the modular runner is **blocked** until complete strict gate/evidence/solver parity has been established.


## [Unreleased] — R10-05 (2026-11-04)

### Correctness / Safety
- EV scenario jobs no longer promote a mesh PASS to overall PASS while independent CFD simulation verification is NOT_RUN.
- Worker exposes fail-closed scenario verdict and `verdict_reason`; existing mesh and physics statuses remain separate.
- EV scenario panel stops interpreting HTTP 200, job COMPLETED or legacy verdict PASS as simulation acceptance.
- Added explicit regression scenarios for missing proof, failed gates, forged/legacy PASS and queue/transport errors.

### Compatibility
- Kept existing JSON status fields and scientific calculations; no FDS/IFC or solver changes.
- Documented evidence contract and limits in `docs/architecture/15-r10-05-scenario-verdict-contract.md`.

## [Unreleased] — R10-06 (2026-11-04)

### Quality infrastructure
- Added dedicated quality CI for Python compilation, targeted Ruff/Pyright, targeted JavaScript ESLint, Python regression tests and coverage evidence.
- Added an AST-based debt inventory and a per-changed-file Git merge-base gate to prevent new function-local imports, broad/bare exceptions and silent exception blocks.
- Coverage is reported without an invented threshold; benchmark and numerical-warning findings remain open pending reproducible baselines.
- Existing Python matrix, browser and pinned FDS solver verification remain unchanged.

See `docs/architecture/17-r10-06-quality-gates.md`.

## [Unreleased] — R10-07 (2026-11-04)

### Input/output correctness
- Added per-mode JSON result contracts for conversion, scenario, preview and inventory jobs.
- The job supervisor now validates result schema and verdict coherence before publishing COMPLETED or promoting to durable.
- Reading persisted result.json validates the same contract again; artifact URLs remain server-owned and whitelisted.
- Added negative tests for forged MAPPING_VERIFIED, unsupported simulation PASS, malformed artifacts, changed result files and worker lifecycle.
- Existing preview download URLs remain supported.

See `docs/architecture/18-r10-07-result-contracts.md`.

## [Unreleased] — R10-08 (2026-11-04)

### Artifact evidence integrity
- Added streamed SHA-256 evidence index for new conversion and scenario job result files.
- Worker publishes index before successful exit; service and result API verify it before COMPLETED, durable or read access.
- Verified mapping results cross-check acceptance report, manifest, audit checkpoint, FDS bytes, geometry index and bundle digest.
- Added regression tests for modified/deleted files and real tiny-IFC artifact consistency.
- Historical convert/scenario jobs without an index now fail closed pending an explicitly reviewed migration.

See `docs/architecture/19-r10-08-evidence-index.md`.
