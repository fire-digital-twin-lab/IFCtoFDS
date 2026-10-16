# ADR 0005 — MappingPlan Decouples Domain Mapping from FDS Serialization

## Status
Accepted.

## Context
Previously, mapping policies and FDS text formatting were intertwined. The exporter directly inspected canonical elements and generated raw text lines like `&OBST ...` without an explicit intermediate contract. This made it impossible to test mapping decisions independently of FDS string syntax, and tied the policy engine to a single output syntax.

## Decision
Introduce an explicit **`MappingPlan`** domain structure:
```text
Canonical Model ──> Mapping Policy ──> MappingPlan ──> FDS Serializer ──> .fds
```
The `MappingPlan` records every element's `MappingDecision` (strategy, representation, primitive IDs, geometric bounds, rationale). The FDS serializer acts purely as a syntax renderer consuming the plan.

## Alternatives Considered
- Direct string serialization in mapping policy: Rejected due to coupling.
- Serializing directly to FDS abstract syntax tree (AST): Rejected as overly complex; `MappingPlan` captures simulation intent without full compiler overhead.

## Consequences
- Mapping decisions can be tested without formatting or parsing FDS text.
- Alternate output formats (e.g. JSON representations, visualization meshes, other CFD engines) can be added by implementing new serializers against `MappingPlan`.
