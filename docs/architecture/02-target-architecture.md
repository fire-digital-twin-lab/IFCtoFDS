# 02 — Target Architecture: Modular Monolith + Hexagonal Architecture

## 1. Architectural Philosophy
The target architecture adopts:
- **Modular Monolith**: One deployable codebase without unnecessary network boundaries, microservices, or distributed queue dependencies.
- **Hexagonal Architecture (Ports & Adapters)**: Pure domain core at the center, surrounded by application use cases, which declare ports implemented by infrastructure adapters.
- **Domain-Oriented Modules**: Bounded contexts for Source, BIM/Canonical, Scope, MEP, Mapping, Validation, and Reference.

## 2. Layered Organization
```text
                         ┌─────────────────────────┐
                         │       Interfaces        │
                         │ CLI / REST API / Worker │
                         └────────────┬────────────┘
                                      │ calls
                                      ▼
                         ┌─────────────────────────┐
                         │       Application       │
                         │ Use Cases / DTO / Ports │
                         └────────────┬────────────┘
                                      │ uses
                                      ▼
┌────────────────────────────────────────────────────────────────┐
│                         DOMAIN CORE                            │
│ Source Model │ Canonical BIM │ Scope/Domain │ Mapping          │
│ Geometry Ref │ MEP Network   │ Provenance   │ Validation Gate  │
│ Golden Ref   │ Acceptance    │ Boundary Policy                 │
│                                                                │
│         ZERO dependencies on FastAPI / IfcOpenShell / FDS      │
└───────────┬──────────────────┬────────────────────┬────────────┘
            ▲                  ▲                    ▲
            │ implements       │ implements         │ implements
    ┌───────┴──────┐   ┌───────┴──────┐     ┌───────┴──────┐
    │ IFC Adapter  │   │ FDS Adapter  │     │ Storage      │
    │ IfcOpenShell │   │ Serializer   │     │ Artifacts    │
    │ Geometry     │   │ Parser       │     │ Reference DB │
    └──────────────┘   │ Solver       │     └──────────────┘
                       └──────────────┘
```

## 3. Benefits
1. **Maintainability**: Independent gate checkers, decoupled serializers, clear module responsibilities.
2. **Interchangeability**: The geometry engine or solver can be substituted without touching mapping rules.
3. **Reproducibility**: Environment execution metadata captured alongside immutable artifacts.
4. **Testability**: Domain logic can be unit-tested without FDS binaries or live IFC files.
