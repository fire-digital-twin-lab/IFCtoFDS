"""Source model and environment provenance domain models."""

from typing import Any, List
from pydantic import BaseModel, Field


class SourceMetadata(BaseModel):
    source_id: str = ""
    filename: str
    file_path: str
    file_hash_sha256: str
    file_size_bytes: int
    schema_version: str  # e.g., "IFC4", "IFC2X3"
    unit_length_name: str = "METRE"
    unit_scale_to_meters: float = 1.0
    world_transform: List[float] = Field(
        default_factory=lambda: [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ]
    )
    rebase_vector: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class SourceIdentity(BaseModel):
    source_id: str
    step_id: int
    global_id: str

    @property
    def entity_key(self) -> str:
        return f"{self.source_id}:{self.step_id}"


class ExecutionEnvironment(BaseModel):
    tool_version: str
    git_sha: str
    schema_version: str
    python_version: str
    platform: str
    dependencies: dict[str, str] = Field(default_factory=dict)
    fds_solver_version: str | None = None
    tolerances: dict[str, Any] = Field(default_factory=dict)
    source_digests: dict[str, str] = Field(default_factory=dict)
