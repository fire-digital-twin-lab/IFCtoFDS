# 01 — Current Architecture Map (As-Is)

## 1. Overview
The IFCtoFDS codebase historically evolved with two parallel pipelines:
1. **JavaScript Web Engine (`js/`)**: A client-side browser pipeline using web-ifc and direct FDS text export workers.
2. **Python Verified Framework (`ifc_to_fds/`)**: A research-grade pipeline using IfcOpenShell, manifold CSG, 3-tier independent validation, and golden reference parity.

## 2. Technical Organization (As-Is)
```text
ifc_to_fds/
├── core/         # Canonical schema, inventory extraction, federation, placement, units
├── geometry/     # IfcOpenShell OCC engine, mesh utilities, package storage
├── mapping/      # Policy planner, boundary handler, FDS text exporter, manifest
├── mep/          # MEP classifier, port graph extraction
├── validation/   # Acceptance report, validation engine, parser, metrics, golden reference, solver
├── pipeline.py   # Monolithic orchestration (convert, audit, prepare, save_artifacts)
├── jobs.py       # Job manager, subprocess worker, queue, lifecycle
└── server.py     # FastAPI endpoints
```

## 3. Identified Architectural Bottlenecks
- `pipeline.py` mixes IFC ingestion, spatial scope, mapping planning, FDS serialization, validation orchestration, and filesystem artifact persistence in a single module.
- `validation/engine.py` (`run_independent_validation`) handles syntax, traceability, geometry, openings, MEP, and solver verification in one massive procedure.
- `AcceptanceReport` acts both as mutable scratch state during verification and final immutable audit artifact.
- Direct tight coupling between mapping policy and FDS syntax serialization without an explicit `MappingPlan` intermediate contract.
- Circular dependencies mitigated by function-local imports across geometry, validation, and mapping.
