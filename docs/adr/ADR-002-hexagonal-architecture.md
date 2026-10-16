# ADR 0002 — Hexagonal Architecture (Ports and Adapters)

## Status
Accepted.

## Context
The core business value of IFCtoFDS lies in its domain models (BIM accounting, MEP graph, spatial scope, boundary policies, mapping decisions, and validation rules). Coupling domain models to specific external technologies (such as IfcOpenShell C++ bindings, FastAPI, or specific FDS binary versions) creates brittle code and prevents swapping or updating infrastructure.

## Decision
Organize the codebase according to **Hexagonal Architecture (Ports & Adapters)**:
- Pure Domain Core at the center, free from framework dependencies.
- Application layer declaring Use Cases and Ports (Protocols).
- Infrastructure Adapters implementing those ports for IfcOpenShell, FDS, filesystem storage, etc.
- Interfaces for CLI, REST API, and worker processes.

## Alternatives Considered
- **Traditional N-tier Layered Architecture**: Rejected because data models often bleed into database/external library dependencies.
- **Clean Architecture / Onion Architecture**: Semantically equivalent; Hexagonal Architecture was chosen for its explicit ports/adapters metaphor.

## Consequences
- Domain logic is testable in isolation without external tools.
- Concrete technologies (IfcOpenShell, FDS, SQLite, FastAPI) can be updated or replaced without rewriting mapping policies.
- Automated architecture tests enforce dependency direction rules.
