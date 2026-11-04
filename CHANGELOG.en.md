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
