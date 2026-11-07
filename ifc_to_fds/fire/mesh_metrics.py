"""Shared fire-source metrics used by mesh evidence and validation."""

from __future__ import annotations

from typing import Any, Dict

from ifc_to_fds.fire.ev_library import load_ev_preset

# Reference constant: rho_inf * c_p * T_inf * sqrt(g)
# 1.204 kg/m3 * 1.005 kJ/(kg K) * 293.15 K * sqrt(9.81 m/s2)
# ~= 1111.4 kW/m^(5/2), matching the project's historical D* implementation.
PLUME_COEFFICIENT = 1111.4


def calculate_d_star(heat_release_rate_kw: float) -> float:
    """Calculate characteristic fire diameter D* in metres."""

    if heat_release_rate_kw <= 0.0:
        return 0.0
    return float((heat_release_rate_kw / PLUME_COEFFICIENT) ** 0.4)


def ev_peak_hrr_evidence(ev: Any) -> Dict[str, Any]:
    """Resolve peak HRR while preserving whether it is explicit or assumed."""

    if hasattr(ev, "peak_hrr_mw") and ev.peak_hrr_mw is not None:
        return {
            "peak_hrr_kw": float(ev.peak_hrr_mw) * 1000.0,
            "peak_hrr_basis": "EXPLICIT_SELECTION",
        }
    if isinstance(ev, dict):
        if ev.get("peak_hrr_kw") is not None:
            return {
                "peak_hrr_kw": float(ev["peak_hrr_kw"]),
                "peak_hrr_basis": "EXPLICIT_SELECTION",
            }
        if ev.get("peak_hrr_mw") is not None:
            return {
                "peak_hrr_kw": float(ev["peak_hrr_mw"]) * 1000.0,
                "peak_hrr_basis": "EXPLICIT_SELECTION",
            }

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
