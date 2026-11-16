"""Shared fire-source metrics used by mesh evidence and validation."""

from __future__ import annotations

from typing import Any, Dict

from ifc_to_fds.domain.validation.plume import PLUME_COEFFICIENT, calculate_d_star, explicit_peak_hrr_evidence
from ifc_to_fds.fire.ev_library import load_ev_preset

__all__ = ["PLUME_COEFFICIENT", "calculate_d_star", "ev_peak_hrr_evidence"]


def ev_peak_hrr_evidence(ev: Any) -> Dict[str, Any]:
    """Resolve peak HRR while preserving whether it is explicit or assumed."""

    explicit = explicit_peak_hrr_evidence(ev)
    if explicit is not None:
        return explicit

    preset_id = getattr(ev, "preset_id", None) or (
        ev.get("preset_id") if isinstance(ev, dict) else None
    )
    if preset_id:
        preset_key = str(preset_id).strip().lower()
        if "-" in preset_key:
            vehicle_class, chemistry = preset_key.rsplit("-", 1)
            preset = load_ev_preset(vehicle_class, chemistry)
            minimum_mw, maximum_mw = preset.peak_hrr_mw_range
            return {
                "peak_hrr_kw": ((minimum_mw + maximum_mw) / 2.0) * 1000.0,
                "peak_hrr_basis": "PRESET_RANGE_MIDPOINT_ASSUMPTION",
                "peak_hrr_range_kw": [
                    minimum_mw * 1000.0,
                    maximum_mw * 1000.0,
                ],
                "preset_id": preset.preset_id,
                "preset_confidence": preset.confidence,
                "preset_citations": [
                    citation.model_dump(mode="json")
                    for citation in preset.citations
                ],
            }

    return {
        "peak_hrr_kw": 0.0,
        "peak_hrr_basis": "UNAVAILABLE",
    }
