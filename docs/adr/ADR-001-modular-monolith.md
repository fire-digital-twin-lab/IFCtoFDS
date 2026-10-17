# ADR 0001 — Modular Monolith Architecture

## Status
Accepted.

## Context
IFCtoFDS requires high maintainability, reproducible research outcomes, and deterministic verification. Distributing the system into microservices (e.g., separate geometry service, mapping service, validation service over network RPC/HTTP) would introduce significant debugging friction, deployment complexity, latency overhead during heavy vertex passing, and risk breaking end-to-end reproducibility.

## Decision
Adopt a **Modular Monolith** structure. All components (ingestion, canonical modeling, mapping, validation, and solver execution) reside in a single deployable repository and process tree, with strictly enforced boundaries between modules.

## Alternatives Considered
- **Microservices**: Rejected due to high DevOps overhead, network latency for multi-megabyte meshes, and difficulty preserving deterministic traceability.
- **Single monolithic pipeline**: Rejected due to tight coupling and unmaintainable monolithic files.

## Consequences
- Single codebase, easy local testing, straightforward CI.
- Modules must communicate via clear internal interfaces rather than ad-hoc imports.
- Subprocesses can still be used for CPU-bound tasks (FDS solver, geometry worker) without microservice overhead.
