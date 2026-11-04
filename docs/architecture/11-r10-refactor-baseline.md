# R10 — Refactor Baseline and Module Boundaries

**Recorded:** 2026-11-04
**Base commit:** `503f692a7047d3b8b1af13107863ed30c5db96b1`
**Scope:** behavior-preserving modularization, no geometry or verdict changes.

## 1. Current state

IFCtoFDS already documents Modular Monolith + Hexagonal Architecture
(ADR-001/002), an authoritative Python Verified Core (ADR-003), and
a non-authoritative JavaScript legacy Quick Path (ADR-004). Existing
`domain/`, `application/`, `adapters/`, `bootstrap/`, `mapping/`,
`geometry/`, `validation/`, `fire/`, `mep/` and `core/` paths
are a **transitional architecture**, not independent finalized modules.

Dependencies that still need separation include:
- `application/use_cases/convert_verified.py` imports concrete
  `mapping.exporter.serialize_fds` and `geometry.storage.write_package`;
- `application/use_cases/audit_conversion.py` calls the legacy
  `validation.engine.run_independent_validation`;
- `validation/runner.py` and `AcceptanceEvaluator` are present but
  must not replace legacy scientific assertions before proof of parity;
- `bootstrap/container.py` creates use cases but does not inject all
  their required ports;
- `js/app-controller.js`, `js/viewer/scene-viewer.js`,
  `js/ifc/ifc-adapter.js`, `js/fds/fds-exporter.js` remain large
  files with mixed responsibilities.

## 2. Proposed module ownership

| Module | Owns | Must not own |
|---|---|---|
| source | source identity, IFC inventory, placement provenance | FDS serialization |
| geometry | source mesh extraction, normalization, opening evidence | acceptance verdict |
| mapping | MappingPlan, strategies, FDS representation decisions | solver execution |
| mep | IFC ports, flow semantics, HVAC network | UI components |
| fire | scenario policy, burners, devices, opening controls | source ingestion |
| verification | independent gate checks, scientific metrics, verdict evaluation | converter-generated truth |
| reference | golden reference bundles, approvals and parity | mutable job state |
| execution | worker lifecycle, artifact storage and checksums | scientific gate policy |
| observability | event codes, structured progress, localized messages | verdict authority |

The existing `ifc_to_fds.observability` package is an incremental,
framework-independent implementation of a cross-cutting diagnostic service.
It does not create a new network service.

## 3. Dependency direction

```text
CLI / HTTP / Browser
       |
       v
Application use cases --(Protocols)--> Adapters
       |
       v
Domain / value objects

Scientific validation independently re-reads source and serialized output.
```

Within a bounded module, lower layers cannot import higher layers.
Cross-module access uses a published contract or application API, not an
internal implementation import.

## 4. Ordered migration gates

1. **R10-00 / baseline:** preserve existing CI (Python, browser, JS, FDS),
   stable artifacts and major real-world regression cases.
2. **R10-01 / diagnostics:** one JSONL event stream, EN/VI view renderers,
   locale tests; no report or FDS data changes.
3. **R10-02 / DI:** inject IFC reader, geometry builder, FDS serializer,
   evidence repository and audit ports into conversion use cases.
4. **R10-03 / validation:** run legacy and micro-checker audits in parallel
   against identical fixtures and compare outcomes/metrics per gate.
5. **R10-04 / frontend:** separate viewer/controller/features and keep
   Portable Preview vs Python Verified Core clearly distinguished.

## 5. Stop-the-line conditions

Any unexplained change in `MAPPING_VERIFIED`/`REJECTED`/`INCONCLUSIVE`,
a missing IFC entity, source hash divergence, altered opening or geometry,
an unreviewed tolerance change, unexpected FDS output, or solver regression
blocks migration. Never map `NOT_RUN` or `INCONCLUSIVE` to `PASS`.

## 6. Two-language documentation policy

Human-facing decisions, changes, and operational messages receive
English and Vietnamese versions. Machine identifiers, status enums,
provenance and acceptance artifacts remain language-independent.

See [EN log guide](../en/observability.md),
[VI log guide](../vi/observability.md), and
[ADR-009](../adr/ADR-009-canonical-bilingual-diagnostic-events.md).
