# 05 — Ports and Adapters Specification

## 1. Application Ports

### 1.1 `ArtifactRepositoryPort` — `[IMPLEMENTED]`
Defined in `ifc_to_fds/application/ports/storage.py` and implemented by `ifc_to_fds/adapters/storage/filesystem.py`:
```python
@runtime_checkable
class ArtifactRepositoryPort(Protocol):
    def save_run_artifacts(self, result: Dict[str, Any], output: Union[str, Path]) -> Dict[str, str]: ...
    def read_artifact(self, path: Union[str, Path]) -> bytes: ...
```

### 1.2 `ReferenceRepositoryPort` & Adapter — `[IMPLEMENTED]`
Implemented by `ifc_to_fds/adapters/reference/filesystem.py`:
```python
class FilesystemReferenceRepository:
    def bundle_digest(self, directory: Path | str) -> str: ...
    def inspect_case(self, directory: Path | str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]: ...
    def resolve_sources(self, case: Path | str, mapping: Dict[str, str]) -> List[Path]: ...
    def save_candidate_bundle(self, directory: Path | str, values: Dict[str, Any]) -> None: ...
```

### 1.3 `JobService` & `JobRepository` — `[IMPLEMENTED]`
Implemented in `ifc_to_fds/adapters/jobs/`:
- `JobRepository`: Thread-safe job state tracking.
- `WorkerRunner`: Subprocess use-case execution runner with stderr capture.
- `JobService`: Queue bounds, lifecycle management, and retention cleanup.

### 1.4 Target Geometry and Serialization Ports — `[TARGET]`
Target ports planned for Phase R10 to replace transitional utility modules:
- `IfcReaderPort`: Wraps `core.federation.load_sources` and `core.inventory`.
- `GeometryEnginePort`: Wraps `geometry.engine.process_model_geometry`.
- `FdsSerializerPort`: Formalizes `mapping.exporter.serialize_fds`.
- `FdsParserPort`: Formalizes `validation.parser.parse_fds`.
- `FdsSolverPort`: Formalizes `validation.solver.solver_gates`.
