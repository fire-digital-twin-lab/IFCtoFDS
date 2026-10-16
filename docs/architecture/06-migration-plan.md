# 06 — Migration Plan: Strangler Fig Pattern

## 1. Principle
Refactoring is strictly behavior-preserving. No logic loss, no algorithm changes, and no syntax rewrites occur simultaneously.

## 2. Strangler Fig Progression
```text
Phase R0: Baseline Blocker Fix & Behavior Freeze
  │  Fix manifest CSV TypeError, add E2E tests, snapshot 6 baseline cases.
  ▼
Phase R1: Architecture Skeleton & Dependency Rules
  │  Create package structure, bootstrap container, AST architecture contract tests.
  ▼
Phase R2: Move Domain Models & Compatibility Re-exports
  │  Move canonical models, value objects, and enums into domain/; keep re-exports.
  ▼
Phase R3: Introduce MappingPlan
  │  Decouple mapping policy decisions from FDS string serialization.
  ▼
Phase R4: Split Pipeline into Application Use Cases
  │  ConvertVerified, AuditConversion, InspectIfc; pipeline.py becomes facade.
  ▼
Phase R5: Split Validation into Gate Checkers
  │  One gate = one checker. AcceptanceEvaluator produces immutable report.
  ▼
Phase R6: Split Golden / Reference Subsystem
  │  Extract candidate creation, parity evaluation, and reference repository.
  ▼
Phase R7: Extract Artifact & Evidence Storage
  │  ArtifactRepository decouples large logs and binary meshes from JSON reports.
  ▼
Phase R8: Split Job System
  │  JobService, WorkerRunner, and JobRepository.
  ▼
Phase R9: Isolate Verified Web vs Legacy Quick Path
  │  Documentation and namespaces distinguishing authoritative core from legacy JS.
  ▼
Phase R10: Reorganize Tests & Parity Verification
     All parity snapshots pass. Compatibility facades safely pruned.
```
