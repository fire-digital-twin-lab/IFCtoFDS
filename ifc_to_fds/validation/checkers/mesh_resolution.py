"""Mesh resolution gate checker for fire scenarios based on plume characteristic diameter D*."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import (
    Finding,
    GateResult,
    GateStatus,
    Severity,
    ValidationContext,
)

# Reference constant: rho_inf * c_p * T_inf * sqrt(g)
# 1.204 * 1.005 * 293.15 * sqrt(9.81) ~= 1111.4
PLUME_COEFFICIENT = 1111.4


def calculate_d_star(heat_release_rate_kw: float) -> float:
    """Calculate characteristic fire diameter D* in meters.

    D* = (Q / (rho_inf * c_p * T_inf * sqrt(g)))^(2/5)
    where denominator is approximately 1111.4 (with Q in kW).
    """
    if heat_release_rate_kw <= 0.0:
        return 0.0
    return float((heat_release_rate_kw / PLUME_COEFFICIENT) ** 0.4)


def check_mesh_resolution(
    scenario: Union[Any, Dict[str, Any]], cell_size: float = 0.2
) -> GateResult:
    """Check whether computational cell size satisfies 4 <= D*/dx <= 16 for fire scenario.

    Parameters
    ----------
    scenario: ScenarioBundle, dict, or numeric peak HRR
        Carries total peak HRR (or individual max peak HRR). If total_peak_hrr_mw
        is in MW, converts to kW (* 1000.0).
    cell_size: float
        Computational mesh cell size in meters (dx). Default 0.2m.

    Returns
    -------
    GateResult with PASS, FAIL, or NOT_APPLICABLE and evidence dict.
    """
    peak_hrr_kw = 0.0

    if hasattr(scenario, "total_peak_hrr_mw"):
        peak_hrr_kw = float(scenario.total_peak_hrr_mw) * 1000.0
    elif isinstance(scenario, dict):
        if "individual_max_peak_hrr_mw" in scenario:
            peak_hrr_kw = float(scenario["individual_max_peak_hrr_mw"]) * 1000.0
        elif "individual_peak_hrr_mw" in scenario:
            peak_hrr_kw = float(scenario["individual_peak_hrr_mw"]) * 1000.0
        elif "individual_max_peak_hrr_kw" in scenario:
            peak_hrr_kw = float(scenario["individual_max_peak_hrr_kw"])
        elif "individual_peak_hrr_kw" in scenario:
            peak_hrr_kw = float(scenario["individual_peak_hrr_kw"])
        elif "total_peak_hrr_mw" in scenario:
            peak_hrr_kw = float(scenario["total_peak_hrr_mw"]) * 1000.0
        elif "peak_hrr_mw" in scenario:
            peak_hrr_kw = float(scenario["peak_hrr_mw"]) * 1000.0
        elif "total_peak_hrr_kw" in scenario:
            peak_hrr_kw = float(scenario["total_peak_hrr_kw"])
        elif "peak_hrr_kw" in scenario:
            peak_hrr_kw = float(scenario["peak_hrr_kw"])
        elif "total_peak_hrr" in scenario:
            val = float(scenario["total_peak_hrr"])
            peak_hrr_kw = val * 1000.0 if val < 50.0 else val
        else:
            raise ValueError(
                "Scenario dict must specify peak HRR (e.g. 'total_peak_hrr_mw' or 'peak_hrr_kw')"
            )
    elif isinstance(scenario, (int, float)):
        val = float(scenario)
        peak_hrr_kw = val * 1000.0 if val < 50.0 else val
    elif hasattr(scenario, "peak_hrr_kw"):
        peak_hrr_kw = float(scenario.peak_hrr_kw)
    else:
        raise TypeError(f"Unsupported scenario type for check_mesh_resolution: {type(scenario)}")

    cell_size = float(cell_size)
    if cell_size <= 0.0:
        return GateResult(
            status=GateStatus.FAIL,
            reason=f"Mesh resolution invalid: cell_size must be positive (> 0), got {cell_size}",
            evidence={"cell_size_m": cell_size},
        )

    if peak_hrr_kw <= 0.0:
        return GateResult(
            status=GateStatus.NOT_APPLICABLE,
            reason="No positive fire HRR for mesh resolution checking",
            evidence={"peak_hrr_kw": peak_hrr_kw, "cell_size_m": cell_size},
        )

    d_star = calculate_d_star(peak_hrr_kw)
    ratio = d_star / cell_size

    evidence = {
        "d_star_m": d_star,
        "cell_size_m": cell_size,
        "d_star_over_dx": ratio,
        "peak_hrr_kw": peak_hrr_kw,
    }

    if ratio < 4.0:
        status = GateStatus.FAIL
        reason = (
            f"Mesh resolution too coarse: D*/dx = {ratio:.2f} < 4.0 "
            f"(cell_size={cell_size:.3f}m, required cell_size <= {d_star / 4.0:.3f}m)"
        )
    elif 4.0 <= ratio <= 16.0:
        status = GateStatus.PASS
        reason = f"Mesh resolution adequate: D*/dx = {ratio:.2f} within [4.0, 16.0]"
    else:
        status = GateStatus.PASS
        reason = f"Mesh resolution very fine: D*/dx = {ratio:.2f} > 16.0"

    return GateResult(
        status=status,
        reason=reason,
        evidence=evidence,
    )


class MeshResolutionChecker:
    """Validation checker verifying computational mesh resolution against fire plume D*."""

    name = "mesh_resolution"

    def check(self, context: ValidationContext, parsed: Any = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        model = context.model
        if parsed is None or model is None:
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="Incomplete diagnostic artifact: FDS text missing",
                ),
                findings=[],
            )

        # Inspect parsed for fire sources: &SURF with HRRPUA/RAMP_Q, &REAC, or fire &VENT
        fire_surfs: Dict[str, float] = {}
        has_reac = False

        if hasattr(parsed, "records"):
            for r in parsed.records:
                if r.kind == "REAC":
                    has_reac = True
                elif r.kind == "SURF":
                    surf_id = str(r.values.get("ID", [""])[0]) if "ID" in r.values else ""
                    if "HRRPUA" in r.values or "RAMP_Q" in r.values:
                        try:
                            val = float(r.values.get("HRRPUA", [0.0])[0])
                            fire_surfs[surf_id] = val
                        except (ValueError, TypeError, IndexError):
                            fire_surfs[surf_id] = 0.0

        # Fallback inspection of raw text if records don't explicitly parse REAC/SURF
        if not fire_surfs and not has_reac and context.fds_text:
            if re.search(r"&(?:REAC|RAMP)\b", context.fds_text, re.IGNORECASE):
                has_reac = True
            m_surf = re.findall(
                r"&SURF\s+ID='([^']+)'[^/]*HRRPUA=([\d.]+)", context.fds_text, re.IGNORECASE
            )
            for sid, hval in m_surf:
                fire_surfs[sid] = float(hval)

        if not fire_surfs and not has_reac:
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(
                    status=GateStatus.NOT_APPLICABLE,
                    reason="No fire sources defined for mesh resolution checking",
                ),
                findings=[],
            )

        # Calculate total fire HRR from HRRPUA * Area or context attributes
        total_hrr_kw = 0.0
        if hasattr(parsed, "records"):
            for r in parsed.records:
                if r.kind == "VENT":
                    surf_id = str(r.values.get("SURF_ID", [""])[0]) if "SURF_ID" in r.values else ""
                    if surf_id in fire_surfs:
                        hrrpua = fire_surfs[surf_id]
                        xb = [float(x) for x in r.values.get("XB", [])]
                        if len(xb) == 6:
                            dx = abs(xb[1] - xb[0])
                            dy = abs(xb[3] - xb[2])
                            dz = abs(xb[5] - xb[4])
                            dims = sorted([dx, dy, dz])
                            area = dims[1] * dims[2]
                            total_hrr_kw += hrrpua * area
                elif r.kind == "OBST":
                    surf_id = str(r.values.get("SURF_ID", [""])[0]) if "SURF_ID" in r.values else ""
                    if surf_id in fire_surfs:
                        hrrpua = fire_surfs[surf_id]
                        xb = [float(x) for x in r.values.get("XB", [])]
                        if len(xb) == 6:
                            dx = abs(xb[1] - xb[0])
                            dy = abs(xb[3] - xb[2])
                            dz = abs(xb[5] - xb[4])
                            area = 2 * (dx * dy + dy * dz + dx * dz)
                            total_hrr_kw += hrrpua * area

        # Context fallbacks if direct geometry association did not resolve total HRR
        if total_hrr_kw <= 0.0:
            if hasattr(context, "scenario") and context.scenario:
                scen = context.scenario
                if hasattr(scen, "total_peak_hrr_mw"):
                    total_hrr_kw = float(scen.total_peak_hrr_mw) * 1000.0
                elif isinstance(scen, dict) and "total_peak_hrr_mw" in scen:
                    total_hrr_kw = float(scen["total_peak_hrr_mw"]) * 1000.0
            elif hasattr(context, "scenario_bundle") and context.scenario_bundle:
                total_hrr_kw = float(context.scenario_bundle.total_peak_hrr_mw) * 1000.0
            elif context.manifest:
                if isinstance(context.manifest, dict):
                    if "total_peak_hrr_mw" in context.manifest:
                        total_hrr_kw = float(context.manifest["total_peak_hrr_mw"]) * 1000.0
                    elif "peak_hrr_kw" in context.manifest:
                        total_hrr_kw = float(context.manifest["peak_hrr_kw"])
                elif hasattr(context.manifest, "total_peak_hrr_mw"):
                    total_hrr_kw = float(context.manifest.total_peak_hrr_mw) * 1000.0

            if total_hrr_kw <= 0.0 and context.fds_text:
                m_peak = re.search(r"! Total Peak HRR:\s*([\d.]+)\s*MW", context.fds_text)
                if m_peak:
                    total_hrr_kw = float(m_peak.group(1)) * 1000.0
                elif fire_surfs:
                    total_hrr_kw = sum(v for v in fire_surfs.values() if v > 0)

        if total_hrr_kw <= 0.0:
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="Fire sources present but unable to determine fire HRR for mesh resolution",
                ),
                findings=[],
            )

        # Determine cell size from MESH records or context.config.cell_size
        mesh_cell_sizes: List[float] = []
        if hasattr(parsed, "records"):
            for r in parsed.records:
                if r.kind == "MESH":
                    xb = [float(x) for x in r.values.get("XB", [])]
                    ijk = [float(x) for x in r.values.get("IJK", [])]
                    if len(xb) == 6 and len(ijk) == 3 and all(n > 0 for n in ijk):
                        dx = abs(xb[1] - xb[0]) / ijk[0]
                        dy = abs(xb[3] - xb[2]) / ijk[1]
                        dz = abs(xb[5] - xb[4]) / ijk[2]
                        mesh_cell_sizes.append(max(dx, dy, dz))

        if mesh_cell_sizes:
            cell_size = max(mesh_cell_sizes)
        elif context.config is not None and getattr(context.config, "cell_size", None) is not None:
            cell_size = float(context.config.cell_size)
        else:
            cell_size = 0.2

        gate_result = check_mesh_resolution(
            {"total_peak_hrr_kw": total_hrr_kw}, cell_size=cell_size
        )

        findings: List[Finding] = []
        if gate_result.status == GateStatus.FAIL:
            findings.append(
                Finding(
                    id="FND-MESH-0001",
                    severity=Severity.P1,
                    category="mesh_resolution",
                    title="Computational mesh resolution too coarse for fire plume",
                    detail=gate_result.reason,
                    element_id="",
                )
            )

        return CheckerOutcome(
            gate_name=self.name,
            result=gate_result,
            findings=findings,
            metrics=gate_result.evidence,
        )
