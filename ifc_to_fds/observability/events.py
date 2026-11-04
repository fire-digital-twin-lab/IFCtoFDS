"""Stable, framework-independent event contract for IFCtoFDS diagnostics."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
LEVELS = frozenset(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))


def utc_timestamp() -> str:
    """Return an unambiguous UTC timestamp for machine-readable events."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class DiagnosticEvent:
    """One canonical event, with language-independent identifiers and values.

    The event code is stable across languages; translations must never modify
    status identifiers, entity keys, evidence IDs or numerical measurements.
    """

    code: str
    level: str
    stage: str
    params: Mapping[str, Any] = field(default_factory=dict)
    job_id: str | None = None
    entity_key: str | None = None
    timestamp: str = field(default_factory=utc_timestamp)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.code.startswith("IFCFDS."):
            raise ValueError("Diagnostic event codes must begin with IFCFDS.")
        if self.level not in LEVELS:
            raise ValueError(f"Unknown diagnostic level: {self.level}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported event schema version: {self.schema_version}")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "level": self.level,
            "code": self.code,
            "stage": self.stage,
            "job_id": self.job_id,
            "entity_key": self.entity_key,
            "params": dict(self.params),
        }
