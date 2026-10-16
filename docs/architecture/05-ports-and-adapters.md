# 05 — Ports and Adapters Specification

## 1. Application Ports
Defined in `ifc_to_fds/application/ports/`:

### 1.1 `IfcReaderPort`
```python
class IfcReaderPort(Protocol):
    def read_model(self, paths: list[str], options: dict[str, Any]) -> CanonicalModel:
        ...
```

### 1.2 `GeometryEnginePort`
```python
class GeometryEnginePort(Protocol):
    def process_geometry(self, model: CanonicalModel) -> CanonicalModel:
        ...
```

### 1.3 `FdsSerializerPort`
```python
class FdsSerializerPort(Protocol):
    def serialize(self, plan: MappingPlan, domain: BoundingBox, cell_size: float) -> tuple[str, MappingManifest]:
        ...
```

### 1.4 `FdsParserPort`
```python
class FdsParserPort(Protocol):
    def parse(self, text: str) -> ParsedFds:
        ...
```

### 1.5 `FdsSolverPort`
```python
class FdsSolverPort(Protocol):
    def execute(self, fds_path: str, timeout_s: float) -> SolverResult:
        ...
```

### 1.6 `ArtifactRepositoryPort`
```python
class ArtifactRepositoryPort(Protocol):
    def save_run_artifacts(self, run_id: str, artifacts: dict[str, Any]) -> dict[str, str]:
        ...
```

### 1.7 `ReferenceRepositoryPort`
```python
class ReferenceRepositoryPort(Protocol):
    def load_case(self, case_id: str) -> dict[str, Any]:
        ...
```

## 2. Infrastructure Adapters
Implemented in `ifc_to_fds/adapters/`:
- `ifc/ifcopenshell/`: Ingestion, placement resolution, units, and OpenCASCADE mesh extraction.
- `fds/serializer/`: Formats `MappingPlan` into valid FDS namelist syntax (`&HEAD`, `&MESH`, `&OBST`, `&GEOM`).
- `fds/parser/`: Robust namelist lexer and parser.
- `fds/solver/`: Local subprocess runner with probe timeouts and stdout/stderr capture.
- `storage/`: Local filesystem implementation with payload hashing and zip archiving.
- `reference/`: File-backed golden reference cases.
