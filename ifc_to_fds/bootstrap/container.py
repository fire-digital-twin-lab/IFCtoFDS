"""Application dependency injection and bootstrap container."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Container:
    """Composition root assembling ports, adapters, and application use cases."""

    config: Optional[dict[str, Any]] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


def create_container(config: Optional[dict[str, Any]] = None) -> Container:
    """Create and configure application container."""
    return Container(config=config)
