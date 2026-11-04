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
