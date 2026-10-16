# 03 — Dependency Rules and Architectural Invariants

## 1. Direction of Dependencies
The fundamental rule of Hexagonal Architecture:
```text
Interfaces ──> Application ──> Domain
                     │
                     │ (declares ports)
                     ▼
                 Adapters (implements ports)
```

## 2. Layer Invariants and Implementation Status

### 2.1 Domain Layer (`ifc_to_fds/domain/`) — `[IMPLEMENTED]`
- **MUST NOT** import `ifcopenshell`.
- **MUST NOT** import `fastapi`, `uvicorn`, `starlette`.
- **MUST NOT** import `subprocess`.
- **MUST NOT** perform filesystem I/O directly.
- **MUST NOT** import concrete adapters or delivery interfaces.
- **MAY** import standard library (`math`, `typing`, `enum`, `dataclasses`, `copy`, `hashlib`) and pure data modeling libraries (`pydantic`).
- *Enforcement:* Verified by automated AST architecture tests in `tests/test_architecture_contracts.py`.

### 2.2 Application Layer (`ifc_to_fds/application/`) — `[TRANSITIONAL]`
- **MAY** import from `domain`.
- **MAY** declare protocols / abstract base classes in `application/ports/`.
- **MUST NOT** directly import concrete adapter implementations (`adapters.*`).
- **MUST NOT** import delivery frameworks (`fastapi`, `uvicorn`, `starlette`).
- *Transitional State:* Application use cases currently interact with transitional internal packages (`geometry.*`, `mapping.*`, `validation.*`) as Strangler Fig progression continues toward Stage R10 ports.

### 2.3 Adapters Layer (`ifc_to_fds/adapters/`) — `[IMPLEMENTED]`
- Implements the ports defined by `application/ports/`.
- Implemented adapters: `adapters/storage` (`LocalFilesystemArtifactRepository`), `adapters/jobs` (`JobService`, `WorkerRunner`, `JobRepository`), `adapters/reference` (`FilesystemReferenceRepository`).
- **MAY** use `ifcopenshell`, `manifold3d`, `trimesh`, `scipy`, `numpy`, `subprocess`, and filesystem I/O (`pathlib`, `shutil`).
- **MUST NOT** be depended upon by `domain`.

### 2.4 Interfaces Layer (`ifc_to_fds/interfaces/`) — `[TRANSITIONAL]`
- Validates delivery input (HTTP payloads, CLI arguments).
- Constructs application DTOs and executes use cases.
- Serializes application results to delivery format (JSON responses, exit codes).
- **MUST NOT** contain mapping or validation business logic.
