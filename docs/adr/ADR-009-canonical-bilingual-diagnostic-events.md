# ADR-009 — Bilingual views over canonical diagnostic events

**Status:** Accepted for incremental R10-01 integration (2026-11-04).

## Decision

- One machine-readable event stream (`events.jsonl`) is authoritative for diagnostics.
- Derive `events.en.log` and `events.vi.log` from the same event identifiers and parameters.
- Keep `progress.json`, `diagnostics.json` and scientific acceptance report contracts unchanged.
- Validate that locale catalogs have identical event codes and interpolation placeholders.
- Never translate verdicts or treat operational logs as independent validation evidence.
- Sidecar write failures must not change IFC-to-FDS conversion behavior.
- These operational sidecars are not part of the mapping manifest hash.

## Trade-offs

Locale catalogs add maintenance work, but permit consistent localized messages.
A future change may introduce concurrent-writer coordination and a localization
bridge to browser diagnostics.

[English guide](../en/observability.md) · [Hướng dẫn tiếng Việt](../vi/observability.md)
