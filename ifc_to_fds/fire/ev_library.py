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

from pydantic import BaseModel, Field, field_validator, model_validator

from ifc_to_fds.geometry.package import digest

EV_LIBRARY_VERSION = "1.0.0"

Confidence = Literal["low", "medium", "high"]


class Citation(BaseModel):
    source: str
    detail: str = ""


def _validate_range_tuple(v: Tuple[float, float], field_name: str) -> Tuple[float, float]:
    if len(v) != 2:
        raise ValueError(f"{field_name} must be a 2-tuple (min, max)")
    min_val, max_val = v
    if min_val < 0.0:
        raise ValueError(f"{field_name} min value must be >= 0.0, got {min_val}")
    if min_val > max_val:
        raise ValueError(f"{field_name} min ({min_val}) must be <= max ({max_val})")
    return v


class SpeciesYields(BaseModel):
    co: Tuple[float, float]
    soot: Tuple[float, float]
    hf: Tuple[float, float]

    @field_validator("co", "soot", "hf")
    @classmethod
    def _validate_yield_ranges(cls, v: Tuple[float, float], info) -> Tuple[float, float]:
        return _validate_range_tuple(v, info.field_name)


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

    @field_validator("pack_kwh_range", "peak_hrr_mw_range", "t_alpha_s")
    @classmethod
    def _validate_preset_ranges(cls, v: Tuple[float, float], info) -> Tuple[float, float]:
        return _validate_range_tuple(v, info.field_name)

    @model_validator(mode="after")
    def _check_assumption_policy(self) -> "EVPreset":
        if self.version != EV_LIBRARY_VERSION:
            raise ValueError(
                f"Unsupported EV library version {self.version!r}, "
                f"expected {EV_LIBRARY_VERSION!r}"
            )
        if self.chemistry.strip().lower() == "unknown" and self.confidence != "low":
            raise ValueError("unknown-origin preset must use confidence 'low'")
        if not self.citations and self.confidence != "low":
            raise ValueError("Preset without citations must use confidence 'low'")
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
    target_dir = library_dir().resolve()
    path = (target_dir / name).resolve()
    if path.parent != target_dir or "/" in name or "\\" in name:
        raise ValueError(f"Path traversal detected: {vehicle_class!r}/{chemistry!r}")
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
