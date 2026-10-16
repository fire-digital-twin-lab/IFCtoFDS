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

## 2. Strict Layer Invariants

### 2.1 Domain Layer (`ifc_to_fds/domain/`)
- **MUST NOT** import `ifcopenshell`.
- **MUST NOT** import `fastapi`, `uvicorn`, `starlette`.
- **MUST NOT** import `subprocess`.
- **MUST NOT** perform filesystem I/O directly.
- **MUST NOT** import concrete adapters or delivery interfaces.
- **MAY** import standard library (`math`, `typing`, `enum`, `dataclasses`, `copy`, `hashlib`) and pure data modeling libraries (`pydantic`).

### 2.2 Application Layer (`ifc_to_fds/application/`)
- **MAY** import from `domain`.
- **MAY** declare protocols / abstract base classes in `application/ports/`.
- **MUST NOT** directly import concrete adapter implementations.
- **MUST NOT** import `fastapi` or `uvicorn`.

### 2.3 Adapters Layer (`ifc_to_fds/adapters/`)
- Implements the ports defined by `application/ports/`.
- **MAY** use `ifcopenshell`, `manifold3d`, `trimesh`, `scipy`, `numpy`, `subprocess`, and filesystem I/O (`pathlib`, `shutil`).
- **MUST NOT** be depended upon by `domain`.

### 2.4 Interfaces Layer (`ifc_to_fds/interfaces/`)
- Validates delivery input (HTTP payloads, CLI arguments).
- Constructs application DTOs and executes use cases.
- Serializes application results to delivery format (JSON responses, exit codes).
- **MUST NOT** contain mapping or validation business logic.
