"""Pure fire-plume metrics shared by the mesh gate (validation) and scenario evidence (fire): no I/O, no presets."""

from __future__ import annotations

from typing import Any, Dict, Optional

# Reference constant: rho_inf * c_p * T_inf * sqrt(g)
# 1.204 kg/m3 * 1.005 kJ/(kg K) * 293.15 K * sqrt(9.81 m/s2)
# ~= 1111.4 kW/m^(5/2), matching the project's historical D* implementation.
PLUME_COEFFICIENT = 1111.4


def calculate_d_star(heat_release_rate_kw: float) -> float:
    """Calculate characteristic fire diameter D* in metres."""

    if heat_release_rate_kw <= 0.0:
        return 0.0
    return float((heat_release_rate_kw / PLUME_COEFFICIENT) ** 0.4)


def explicit_peak_hrr_evidence(ev: Any) -> Optional[Dict[str, Any]]:
    """Peak HRR the selection states itself, or None when it only names a preset."""

    if hasattr(ev, "peak_hrr_mw") and ev.peak_hrr_mw is not None:
        return {"peak_hrr_kw": float(ev.peak_hrr_mw) * 1000.0, "peak_hrr_basis": "EXPLICIT_SELECTION"}
    if isinstance(ev, dict):
        if ev.get("peak_hrr_kw") is not None:
            return {"peak_hrr_kw": float(ev["peak_hrr_kw"]), "peak_hrr_basis": "EXPLICIT_SELECTION"}
        if ev.get("peak_hrr_mw") is not None:
            return {"peak_hrr_kw": float(ev["peak_hrr_mw"]) * 1000.0, "peak_hrr_basis": "EXPLICIT_SELECTION"}
    return None
