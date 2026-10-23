"""Checkpoint data prepared by a workflow, independent of its model helpers."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckpointPayload:
    inventory: dict[str, Any]
    mep_graph: dict[str, Any]
    configuration: dict[str, Any]


ARTIFACTS = {
    "fds": "model.fds",
    "manifest": "model_manifest.json",
    "manifest_csv": "model_manifest.csv",
    "report": "model_acceptance_report.json",
    "markdown": "model_acceptance_report.md",
    "inventory": "model_inventory.json",
    "mep": "model_mep_graph.json",
    "configuration": "model_configuration.json",
    "geometry": "model_geometry.json",
    "geometry_archive": "model_geometry.zip",
    "parity": "model_parity.json",
    "checksums": "model_checksums.json",
}
