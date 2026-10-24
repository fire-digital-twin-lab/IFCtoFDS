"""EV fire physics library: versioned, checksum-bound preset records.

Each preset is one JSON file per (vehicle_class, chemistry) under
``reference-cases/ev-library/``. Records carry ranges (not point values),
species yields, citations and a confidence level. Presets without
experimental backing must use ``confidence: "low"`` with explicit
assumption notes; ``unknown``-chemistry presets are rejected unless low.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Literal, Tuple

from pydantic import BaseModel, Field, model_validator

from ifc_to_fds.geometry.package import digest

EV_LIBRARY_VERSION = "1.0.0"

Confidence = Literal["low", "medium", "high"]


class Citation(BaseModel):
    source: str
    detail: str = ""


class SpeciesYields(BaseModel):
    co: Tuple[float, float]
    soot: Tuple[float, float]
    hf: Tuple[float, float]


class EVPreset(BaseModel):
    version: str = EV_LIBRARY_VERSION
    vehicle_class: str
    chemistry: str
    pack_kwh_range: Tuple[float, float]
    peak_hrr_mw_range: Tuple[float, float]
    t_alpha_s: Tuple[float, float]
    growth: str
    yields: SpeciesYields
    citations: List[Citation] = Field(default_factory=list)
    confidence: Confidence
    notes: str = ""

    @model_validator(mode="after")
    def _check_assumption_policy(self) -> "EVPreset":
        if self.version != EV_LIBRARY_VERSION:
            raise ValueError(
                f"Unsupported EV library version {self.version!r}, "
                f"expected {EV_LIBRARY_VERSION!r}"
            )
        if self.chemistry.strip().lower() == "unknown" and self.confidence != "low":
            raise ValueError("unknown-origin preset must use confidence 'low'")
        return self

    @property
    def preset_id(self) -> str:
        return f"{self.vehicle_class.strip().lower()}-{self.chemistry.strip().lower()}"


def library_dir() -> Path:
    override = os.environ.get("IFCFDS_EV_LIBRARY_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "reference-cases" / "ev-library"


def load_ev_preset(vehicle_class: str, chemistry: str) -> EVPreset:
    name = f"{vehicle_class.strip().lower()}-{chemistry.strip().lower()}.json"
    path = library_dir() / name
    if not path.is_file():
        raise ValueError(
            f"Unknown EV preset {vehicle_class!r}/{chemistry!r} (missing {name})"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid EV preset JSON {name}: {exc}") from exc
    return EVPreset.model_validate(payload)


def list_ev_presets() -> List[str]:
    directory = library_dir()
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def library_digest() -> str:
    directory = library_dir()
    files: Dict[str, object] = {}
    for path in sorted(directory.glob("*.json")):
        files[path.name] = json.loads(path.read_text(encoding="utf-8"))
    if not files:
        raise ValueError(f"EV library is empty: {directory}")
    return digest(files)
