"""Mesh resolution gate checker for fire scenarios based on plume characteristic diameter D*."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Union

from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import (
    GateResult,
    GateStatus,
    ValidationContext,
)

from ifc_to_fds.fire.mesh_metrics import calculate_d_star, ev_peak_hrr_evidence

def _indicator_band(ratio: float) -> str:
    """Describe D*/dx without turning historical validation values into acceptance limits."""

    if ratio < 4.0:
        return "BELOW_HISTORICAL_4_16_SUBSET"
    if ratio <= 16.0:
        return "WITHIN_HISTORICAL_4_16_SUBSET"
    return "ABOVE_HISTORICAL_4_16_SUBSET"


def _geometry_resolution_metrics(
    scenario: Union[Any, Dict[str, Any]],
    cell_size: float,
) -> List[Dict[str, Any]]:
    """Report critical EV geometry cell counts without inventing acceptance thresholds."""

    raw = getattr(scenario, "vehicle_geometries", None)
    if raw is None and isinstance(scenario, dict):
        raw = scenario.get("vehicle_geometries")
    metrics: List[Dict[str, Any]] = []
    for index, geometry in enumerate(raw or []):
        if hasattr(geometry, "model_dump"):
            data = geometry.model_dump()
        elif isinstance(geometry, dict):
            data = geometry
        else:
            continue

        clearance = data.get("ground_clearance_m")
        battery = data.get("battery_bounds")
        battery_thickness = None
        if isinstance(battery, dict):
            try:
                battery_thickness = float(battery["zmax"]) - float(battery["zmin"])
            except (KeyError, TypeError, ValueError):
                battery_thickness = None

        entry: Dict[str, Any] = {"vehicle_index": index}
        if clearance is not None:
            clearance = float(clearance)
            if math.isfinite(clearance) and clearance > 0.0:
                entry["ground_clearance_m"] = clearance
                entry["ground_clearance_over_dx"] = clearance / cell_size
        if (
            battery_thickness is not None
            and math.isfinite(battery_thickness)
            and battery_thickness > 0.0
        ):
            entry["battery_thickness_m"] = battery_thickness
            entry["battery_thickness_over_dx"] = battery_thickness / cell_size
        if len(entry) > 1:
            metrics.append(entry)
    return metrics


def _indicator_gate(
    evaluations: List[Dict[str, Any]],
    *,
    evidence_key: str,
    geometry_metrics: Optional[List[Dict[str, Any]]] = None,
) -> GateResult:
    """Return an evidence-only mesh gate until grid sensitivity is available."""

    first = evaluations[0]
    evidence: Dict[str, Any] = {
        "d_star_m": first["d_star_m"],
        "cell_size_m": first["cell_size_m"],
        "d_star_over_dx": first["d_star_over_dx"],
        "peak_hrr_kw": first["peak_hrr_kw"],
        evidence_key: evaluations,
        "scientific_interpretation": "INDICATOR_ONLY",
        "historical_4_16_is_acceptance_rule": False,
        "grid_sensitivity_required": True,
        "reference": "NIST_FDS_VALIDATION_GUIDE_6_11_1",
        "cell_size_basis": "CALLER_SUPPLIED_UNVERIFIED_LOCALITY",
        "local_source_mesh_resolved": False,
    }
    if geometry_metrics:
        evidence["critical_geometry_resolution"] = geometry_metrics
    return GateResult(
        status=GateStatus.INCONCLUSIVE,
        reason=(
            "D*/dx is reported as a plume-resolution indicator only; current FDS "
            "validation studies span a wide range of D*/dx values. Mesh adequacy "
            "requires scenario-specific grid sensitivity and relevant geometry "
            "resolution evidence before PASS can be issued."
        ),
        evidence=evidence,
    )


def check_mesh_resolution(
    scenario: Union[Any, Dict[str, Any]], cell_size: float = 0.2
) -> GateResult:
    """Report D*/dx and critical geometry cell counts without using a universal band.

    D*/dx is a useful comparison indicator, not a standalone scientific acceptance
    criterion. This helper therefore remains INCONCLUSIVE for positive-fire cases
    until a later MeshPlan/grid-sensitivity work package supplies the missing
    solution-verification evidence.
    """

    cell_size = float(cell_size)
    if not math.isfinite(cell_size) or cell_size <= 0.0:
        return GateResult(
            status=GateStatus.FAIL,
            reason=(
                "Mesh resolution invalid: cell_size must be finite and positive "
                f"(> 0), got {cell_size}"
            ),
            evidence={"cell_size_m": cell_size},
        )

    ev_selections = getattr(scenario, "ev_selections", None) or (
        scenario.get("ev_selections") if isinstance(scenario, dict) else None
    )
    if ev_selections:
        evaluations: List[Dict[str, Any]] = []
        for idx, ev in enumerate(ev_selections):
            ev_id = getattr(ev, "id", None) or getattr(ev, "preset_id", None)
            if not ev_id and isinstance(ev, dict):
                ev_id = ev.get("id") or ev.get("preset_id")
            if not ev_id:
                ev_id = f"vehicle_{idx}"

            hrr_evidence = ev_peak_hrr_evidence(ev)
            hrr_kw = float(hrr_evidence["peak_hrr_kw"])
            if not math.isfinite(hrr_kw):
                return GateResult(
                    status=GateStatus.FAIL,
                    reason=f"Nonfinite peak HRR for vehicle '{ev_id}'",
                    evidence={"vehicle": ev_id, **hrr_evidence},
                )
            d_star = calculate_d_star(hrr_kw)
            ratio = d_star / cell_size if hrr_kw > 0.0 else 0.0
            evaluations.append(
                {
                    "vehicle": ev_id,
                    **hrr_evidence,
                    "d_star_m": d_star,
                    "cell_size_m": cell_size,
                    "d_star_over_dx": ratio,
                    "indicator_band": _indicator_band(ratio),
                }
            )

        positive = [item for item in evaluations if item["peak_hrr_kw"] > 0.0]
        if not positive:
            return GateResult(
                status=GateStatus.NOT_APPLICABLE,
                reason="No positive fire HRR for mesh resolution checking",
                evidence={"ev_evaluations": evaluations, "cell_size_m": cell_size},
            )
        return _indicator_gate(
            positive,
            evidence_key="ev_evaluations",
            geometry_metrics=_geometry_resolution_metrics(scenario, cell_size),
        )

    peak_hrr_kw = 0.0
    if isinstance(scenario, dict):
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
            raise ValueError(
                "Ambiguous key 'total_peak_hrr' without unit suffix is rejected. "
                "Specify 'peak_hrr_kw' or 'total_peak_hrr_mw'."
            )
        else:
            raise ValueError(
                "Scenario dict must specify peak HRR with explicit unit "
                "(e.g. 'total_peak_hrr_mw' or 'peak_hrr_kw')"
            )
    elif hasattr(scenario, "total_peak_hrr_mw"):
        peak_hrr_kw = float(getattr(scenario, "total_peak_hrr_mw")) * 1000.0
    elif isinstance(scenario, (int, float)):
        raise TypeError(
            "Scalar number for scenario HRR is ambiguous without unit. "
            "Pass a dict specifying 'peak_hrr_kw' or 'total_peak_hrr_mw'."
        )
    elif hasattr(scenario, "peak_hrr_kw"):
        peak_hrr_kw = float(scenario.peak_hrr_kw)
    else:
        raise TypeError(
            f"Unsupported scenario type for check_mesh_resolution: {type(scenario)}"
        )

    if not math.isfinite(peak_hrr_kw):
        return GateResult(
            status=GateStatus.FAIL,
            reason="Mesh indicator input has nonfinite peak HRR",
            evidence={"peak_hrr_kw": peak_hrr_kw, "cell_size_m": cell_size},
        )

    if peak_hrr_kw <= 0.0:
        return GateResult(
            status=GateStatus.NOT_APPLICABLE,
            reason="No positive fire HRR for mesh resolution checking",
            evidence={"peak_hrr_kw": peak_hrr_kw, "cell_size_m": cell_size},
        )

    d_star = calculate_d_star(peak_hrr_kw)
    ratio = d_star / cell_size
    evaluation = {
        "id": "aggregate_or_single_source",
        "peak_hrr_kw": peak_hrr_kw,
        "d_star_m": d_star,
        "cell_size_m": cell_size,
        "d_star_over_dx": ratio,
        "indicator_band": _indicator_band(ratio),
    }
    return _indicator_gate(
        [evaluation],
        evidence_key="source_evaluations",
        geometry_metrics=_geometry_resolution_metrics(scenario, cell_size),
    )


class MeshResolutionChecker:
    """Validation checker verifying computational mesh resolution against fire plume D*."""

    name = "mesh_resolution"

    def check(self, context: ValidationContext, parsed: Any = None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed
        if parsed is None:
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

        # Keep full MESH geometry so source-local spacing can be resolved.
        mesh_specs: List[Dict[str, Any]] = []
        if hasattr(parsed, "records"):
            for r in parsed.records:
                if r.kind == "MESH":
                    xb = [float(x) for x in r.values.get("XB", [])]
                    ijk = [float(x) for x in r.values.get("IJK", [])]
                    if len(xb) == 6 and len(ijk) == 3 and all(n > 0 for n in ijk):
                        spacing = (
                            abs(xb[1] - xb[0]) / ijk[0],
                            abs(xb[3] - xb[2]) / ijk[1],
                            abs(xb[5] - xb[4]) / ijk[2],
                        )
                        mesh_specs.append(
                            {
                                "id": r.id or "<anonymous>",
                                "xb": xb,
                                "cell_size_xyz_m": spacing,
                                "max_spacing_m": max(spacing),
                            }
                        )

        if mesh_specs:
            cell_size = max(mesh["max_spacing_m"] for mesh in mesh_specs)
            cell_size_basis = "GLOBAL_MAX_MESH_SPACING_NOT_SOURCE_LOCAL"
        elif context.config is not None and getattr(context.config, "cell_size", None) is not None:
            cell_size = float(getattr(context.config, "cell_size"))
            cell_size_basis = "CONFIGURED_CELL_SIZE_NOT_SOURCE_LOCAL"
        else:
            cell_size = 0.2
            cell_size_basis = "LEGACY_DEFAULT_0_2M_NOT_SOURCE_LOCAL"

        # Collect individual burner sources from geometry (&VENT / &OBST)
        burner_sources: List[Dict[str, Any]] = []
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
                            if area > 0:
                                vent_id = str(r.values.get("ID", [""])[0]) if "ID" in r.values else surf_id
                                burner_sources.append({
                                    "id": vent_id or surf_id,
                                    "surf_id": surf_id,
                                    "hrrpua": hrrpua,
                                    "area": area,
                                    "hrr_kw": hrrpua * area,
                                    "xb": list(xb),
                                    "centroid": [
                                        (xb[0] + xb[1]) / 2.0,
                                        (xb[2] + xb[3]) / 2.0,
                                        (xb[4] + xb[5]) / 2.0,
                                    ],
                                })
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
                            if area > 0:
                                obst_id = str(r.values.get("ID", [""])[0]) if "ID" in r.values else surf_id
                                burner_sources.append({
                                    "id": obst_id or surf_id,
                                    "surf_id": surf_id,
                                    "hrrpua": hrrpua,
                                    "area": area,
                                    "hrr_kw": hrrpua * area,
                                    "xb": list(xb),
                                    "centroid": [
                                        (xb[0] + xb[1]) / 2.0,
                                        (xb[2] + xb[3]) / 2.0,
                                        (xb[4] + xb[5]) / 2.0,
                                    ],
                                })

        # If burners exist, resolve spacing only when the complete burner
        # extent lies strictly inside exactly one MESH. Centroid-only lookup can
        # overclaim locality when a burner spans a coarse/fine interface.
        if burner_sources:
            evaluations: List[Dict[str, Any]] = []
            for burner in burner_sources:
                hrr_kw = burner["hrr_kw"]
                centroid = burner["centroid"]
                source_xb = burner["xb"]
                local_matches = []
                for mesh in mesh_specs:
                    mesh_xb = mesh["xb"]
                    if all(
                        mesh_xb[2 * axis] + 1e-9
                        < source_xb[2 * axis]
                        and source_xb[2 * axis + 1]
                        < mesh_xb[2 * axis + 1] - 1e-9
                        for axis in range(3)
                    ):
                        local_matches.append(mesh)

                if len(local_matches) == 1:
                    local_mesh = local_matches[0]
                    source_cell_size = local_mesh["max_spacing_m"]
                    source_basis = "BURNER_EXTENT_UNIQUE_MESH"
                    local_resolved = True
                    local_mesh_id = local_mesh["id"]
                    local_xyz = local_mesh["cell_size_xyz_m"]
                else:
                    source_cell_size = cell_size
                    source_basis = cell_size_basis
                    local_resolved = False
                    local_mesh_id = None
                    local_xyz = None

                d_star = calculate_d_star(hrr_kw)
                ratio = d_star / source_cell_size if hrr_kw > 0.0 else 0.0
                item: Dict[str, Any] = {
                    "id": burner["id"],
                    "hrr_kw": hrr_kw,
                    "peak_hrr_kw": hrr_kw,
                    "d_star_m": d_star,
                    "cell_size_m": source_cell_size,
                    "d_star_over_dx": ratio,
                    "indicator_band": _indicator_band(ratio),
                    "source_centroid_m": centroid,
                    "source_extent_xb": list(source_xb),
                    "cell_size_basis": source_basis,
                    "local_source_mesh_resolved": local_resolved,
                    "local_mesh_id": local_mesh_id,
                    "mesh_match_count": len(local_matches),
                }
                if local_xyz is not None:
                    item["local_cell_size_xyz_m"] = list(local_xyz)
                evaluations.append(item)

            gate_result = _indicator_gate(
                evaluations,
                evidence_key="burner_evaluations",
            )
            all_local = all(
                item["local_source_mesh_resolved"] for item in evaluations
            )
            gate_result.evidence["cell_size_basis"] = (
                "PER_BURNER_EXTENT_UNIQUE_MESH"
                if all_local
                else cell_size_basis
            )
            gate_result.evidence["local_source_mesh_resolved"] = all_local
            return CheckerOutcome(
                gate_name=self.name,
                result=gate_result,
                findings=[],
                metrics=gate_result.evidence,
            )

        # Context fallbacks if burning area could not be determined from geometry
        scen = getattr(context, "scenario", None) or getattr(context, "scenario_bundle", None)
        if scen:
            gate_result = check_mesh_resolution(scen, cell_size=cell_size)
            gate_result.evidence["cell_size_basis"] = cell_size_basis
            gate_result.evidence["local_source_mesh_resolved"] = False
            return CheckerOutcome(
                gate_name=self.name,
                result=gate_result,
                findings=[],
                metrics=gate_result.evidence,
            )

        if context.manifest:
            if isinstance(context.manifest, dict):
                manifest_hrr = context.manifest.get("total_peak_hrr_mw") or context.manifest.get("peak_hrr_kw")
            else:
                manifest_hrr = getattr(context.manifest, "total_peak_hrr_mw", None) or getattr(context.manifest, "peak_hrr_kw", None)
            if manifest_hrr:
                gate_result = check_mesh_resolution(context.manifest, cell_size=cell_size)
                gate_result.evidence["cell_size_basis"] = cell_size_basis
                gate_result.evidence["local_source_mesh_resolved"] = False
                return CheckerOutcome(
                    gate_name=self.name,
                    result=gate_result,
                    findings=[],
                    metrics=gate_result.evidence,
                )

        if context.fds_text:
            m_peak = re.search(r"! Total Peak HRR:\s*([\d.]+)\s*MW", context.fds_text)
            if m_peak:
                total_hrr_kw = float(m_peak.group(1)) * 1000.0
                gate_result = check_mesh_resolution(
                    {"total_peak_hrr_kw": total_hrr_kw},
                    cell_size=cell_size,
                )
                gate_result.evidence["cell_size_basis"] = cell_size_basis
                gate_result.evidence["local_source_mesh_resolved"] = False
                return CheckerOutcome(
                    gate_name=self.name,
                    result=gate_result,
                    findings=[],
                    metrics=gate_result.evidence,
                )

        # Dimensional fallback: cannot determine burning area for HRR calculation
        return CheckerOutcome(
            gate_name=self.name,
            result=GateResult(
                status=GateStatus.INCONCLUSIVE,
                reason="Cannot determine burning area for HRR calculation",
            ),
            findings=[],
        )
