# Bilingual diagnostics and event logs (R10-01)

## Goal

IFCtoFDS stores **one canonical event stream** as JSONL and derives
**two human-readable representations** in English and Vietnamese.
Audit statuses, measurements, source SHA hashes, entity keys, and evidence
must not be translated or modified based on the selected language.

## Files in each job directory

- `progress.json`: existing progress contract, unchanged.
- `events.jsonl`: version 1.0 structured canonical event stream.
- `events.en.log`: English rendering of the same event stream.
- `events.vi.log`: Vietnamese rendering of the same event stream.

Events include `schema_version`, UTC `timestamp`, `level`, `code`,
`stage`, `job_id`, `entity_key` and `params`. Do not place large
meshes, full stack traces, API secrets or IFC source data in event params.

## Message catalog

Stable event IDs use the pattern `IFCFDS.<COMPONENT>.<EVENT>`, for
example `IFCFDS.STAGE.COMPLETED`. Translation catalogs live in
`ifc_to_fds/observability/locales/en.json` and `vi.json`.
Contract tests require identical event IDs and placeholder names.

Machine statuses (`PASS`, `FAIL`, `INCONCLUSIVE`, `NOT_RUN`,
`MAPPING_VERIFIED`) stay unchanged in artifacts and JSON APIs.
Localized logs do not substitute for independent audit evidence.

## Python usage

```python
from ifc_to_fds.observability import DiagnosticEvent, append_event

append_event(job_directory, DiagnosticEvent(
    code="IFCFDS.STAGE.COMPLETED",
    level="INFO",
    stage="GEOMETRY",
    params={"stage": "GEOMETRY", "elapsed_s": 1.25},
))
```

Existing `progress()` now emits corresponding structured stage events
without changing the `progress.json` schema. A sidecar logging failure
issues a warning but must not change conversion results. If derived logs
are interrupted partway through writing, rebuild both from the canonical
stream:

```python
from ifc_to_fds.observability import rebuild_localized_logs
rebuild_localized_logs(job_directory)
```

## Scope

This is the initial phase; it does **not** yet localize the full JavaScript
UI, all API errors, or FDS solver output. The human-readable logs remain
sidecars rather than checksummed research artifacts. Do not edit canonical
JSONL manually or use translations for scientific acceptance.

[Phiên bản tiếng Việt](../vi/observability.md)
