"""EV fire scenario emitter: generates standard FDS 6+ fire scenarios.

Consumes verified mapping plans and EV preset physics to produce self-contained
FDS scenario bundles with &REAC, &RAMP, &SURF, &OBST, &VENT, &DEVC, &CTRL namelists.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

from ifc_to_fds.domain.mapping import MappingPlan
from ifc_to_fds.fire.ev_library import EV_LIBRARY_VERSION, EVPreset, load_ev_preset


def clean_fds_id(name: str, fallback: str = "ID") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "")
    cleaned = cleaned.strip("._-")
    if not cleaned:
        cleaned = fallback
    return cleaned[:30]


def format_xb(xb: List[float] | Tuple[float, ...]) -> str:
    return ",".join(
        str(int(v)) if float(v).is_integer() else f"{float(v):.4f}".rstrip("0").rstrip(".")
        for v in xb
    )


class EVSelection(BaseModel):
    preset_id: str
    position: Tuple[float, float, float]
    ignition_delay_s: float = 0.0
    dimensions: Optional[Tuple[float, float, float]] = None
    pack_kwh: Optional[float] = None
    peak_hrr_mw: Optional[float] = None

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(
        cls, v: Optional[Tuple[float, float, float]]
    ) -> Optional[Tuple[float, float, float]]:
        if v is not None:
            if len(v) != 3 or any(d <= 0.0 or not math.isfinite(d) for d in v):
                raise ValueError("EV dimensions (dx, dy, dz) must be strictly positive (> 0.0)")
        return v


class DeviceSelection(BaseModel):
    id: str
    device_type: str
    position: Tuple[float, float, float]
    setpoint: float
    quantity: str


class OpeningEvent(BaseModel):
    entity_key: str
    state: str
    event_time_s: float


class ScenarioBundle(BaseModel):
    scenario_id: str
    bundle_sha256: str
    ev_library_version: str
    fds_fragment: str
    total_peak_hrr_mw: float
    ev_count: int
    ev_selections: List[EVSelection] = Field(default_factory=list)
    devices: List[DeviceSelection] = Field(default_factory=list)
    opening_events: List[OpeningEvent] = Field(default_factory=list)


def _resolve_preset(preset_id: str) -> EVPreset:
    if "-" in preset_id:
        vclass, chem = preset_id.rsplit("-", 1)
        return load_ev_preset(vclass, chem)
    raise ValueError(
        f"Invalid preset_id format: {preset_id!r}, expected 'vehicle_class-chemistry'"
    )


def _normalize_opening_events(opening_states: Optional[Dict[str, Any]]) -> List[OpeningEvent]:
    if not opening_states:
        return []
    events: List[OpeningEvent] = []
    for key, val in opening_states.items():
        if isinstance(val, OpeningEvent):
            events.append(val)
        elif isinstance(val, dict):
            state = str(val.get("state", "CLOSED")).upper()
            raw_time = val.get("event_time_s", val.get("eventTime", 0.0))
            event_time = float(raw_time if raw_time is not None else 0.0)
            entity_key = str(val.get("entity_key", key))
            events.append(OpeningEvent(entity_key=entity_key, state=state, event_time_s=event_time))
        elif isinstance(val, str):
            state = val.strip().upper()
            events.append(OpeningEvent(entity_key=key, state=state, event_time_s=0.0))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, OpeningEvent):
                    events.append(item)
                elif isinstance(item, dict):
                    events.append(OpeningEvent.model_validate(item))
    return events


def emit_fire_scenario(
    mapping_plan: MappingPlan,
    bundle_sha256: str,
    ev_selections: List[EVSelection],
    opening_states: Optional[Dict[str, Any]] = None,
    devices: Optional[List[DeviceSelection]] = None,
    verification_status: str = "MAPPING_VERIFIED",
) -> ScenarioBundle:
    """Emits an FDS fire scenario bundle adhering to strict verification invariants."""
    if (
        verification_status != "MAPPING_VERIFIED"
        or not bundle_sha256
        or str(bundle_sha256).strip().lower() == "stale"
    ):
        raise ValueError("MAPPING_VERIFIED required to emit fire scenario")

    if not ev_selections:
        raise ValueError("At least one EV selection is required")

    normalized_evs = [
        ev if isinstance(ev, EVSelection) else EVSelection.model_validate(ev)
        for ev in ev_selections
    ]
    normalized_devices = [
        d if isinstance(d, DeviceSelection) else DeviceSelection.model_validate(d)
        for d in (devices or [])
    ]
    normalized_opening_events = _normalize_opening_events(opening_states)

    resolved_presets: Dict[str, EVPreset] = {}
    ev_configs: List[Dict[str, Any]] = []
    total_peak_hrr_mw = 0.0

    for ev in normalized_evs:
        preset_key = ev.preset_id.strip().lower()
        if preset_key not in resolved_presets:
            resolved_presets[preset_key] = _resolve_preset(ev.preset_id)
        preset = resolved_presets[preset_key]

        # Validate pack_kwh
        if ev.pack_kwh is not None:
            min_kwh, max_kwh = preset.pack_kwh_range
            if not (min_kwh <= ev.pack_kwh <= max_kwh):
                raise ValueError(
                    f"Custom pack_kwh {ev.pack_kwh} out of preset range {preset.pack_kwh_range}"
                )
            actual_kwh = ev.pack_kwh
        else:
            actual_kwh = (preset.pack_kwh_range[0] + preset.pack_kwh_range[1]) / 2.0

        # Validate peak_hrr_mw
        if ev.peak_hrr_mw is not None:
            min_hrr, max_hrr = preset.peak_hrr_mw_range
            if not (min_hrr <= ev.peak_hrr_mw <= max_hrr):
                raise ValueError(
                    f"Custom peak_hrr_mw {ev.peak_hrr_mw} out of preset range {preset.peak_hrr_mw_range}"
                )
            actual_peak_hrr = ev.peak_hrr_mw
        else:
            actual_peak_hrr = (preset.peak_hrr_mw_range[0] + preset.peak_hrr_mw_range[1]) / 2.0

        # Resolve dimensions
        if ev.dimensions is not None:
            dx, dy, dz = ev.dimensions
        else:
            if "auto" in ev.preset_id.lower() or preset.vehicle_class.lower() == "auto":
                dx, dy, dz = (4.5, 1.8, 1.5)
            else:
                dx, dy, dz = (1.8, 0.6, 1.1)

        total_peak_hrr_mw += actual_peak_hrr
        ev_configs.append(
            {
                "ev": ev,
                "preset": preset,
                "preset_key": preset_key,
                "actual_kwh": actual_kwh,
                "actual_peak_hrr": actual_peak_hrr,
                "dx": dx,
                "dy": dy,
                "dz": dz,
            }
        )

    lines: List[str] = [
        "! ==========================================================================",
        "! EV Fire Scenario Fragment (Generated by IFCtoFDS Task 3 Scenario Emitter)",
        f"! Base Mapping Bundle SHA256: {bundle_sha256}",
        f"! EV Library Version: {EV_LIBRARY_VERSION}",
        f"! Total Peak HRR: {total_peak_hrr_mw:.4f} MW",
        "! ==========================================================================",
        "",
    ]

    # 1. &REAC namelists (one per unique preset)
    # Note: HF (hydrogen fluoride) yields from EV battery chemistry are captured in metadata
    # for toxic exposure evaluation and omitted from single-step FDS &REAC namelists.
    lines.append("! --- Combustion Reaction Namelists ---")
    preset_fuel_ids: Dict[str, str] = {}
    for preset_key, preset in resolved_presets.items():
        reac_id = clean_fds_id(f"REAC_{preset.preset_id.upper()}")
        fuel_id = clean_fds_id(f"OFFGAS_{reac_id}")
        preset_fuel_ids[preset_key] = fuel_id
        co_yield = (preset.yields.co[0] + preset.yields.co[1]) / 2.0
        soot_yield = (preset.yields.soot[0] + preset.yields.soot[1]) / 2.0
        lines.append(
            f"&REAC ID='{reac_id}', FUEL='{fuel_id}', C=2.0, H=4.0, O=1.0, "
            f"CO_YIELD={co_yield:g}, SOOT_YIELD={soot_yield:g} /"
        )
    lines.append("")

    # 2. EV Fire Sources: RAMP, SURF, OBST, VENT
    lines.append("! --- EV Physical Obstacles and Fire Sources ---")
    for idx, cfg in enumerate(ev_configs, start=1):
        ev: EVSelection = cfg["ev"]
        preset: EVPreset = cfg["preset"]
        actual_peak_hrr: float = cfg["actual_peak_hrr"]
        dx, dy, dz = cfg["dx"], cfg["dy"], cfg["dz"]

        cx, cy, cz = ev.position
        xmin = round(cx - dx / 2.0, 4)
        xmax = round(cx + dx / 2.0, 4)
        ymin = round(cy - dy / 2.0, 4)
        ymax = round(cy + dy / 2.0, 4)
        zmin = round(cz - dz / 2.0, 4)
        zmax = round(cz + dz / 2.0, 4)

        burning_area = dx * dy
        hrrpua_kw_m2 = (actual_peak_hrr * 1000.0) / burning_area

        ramp_id = clean_fds_id(f"RAMP_EV_{idx}")
        surf_id = clean_fds_id(f"BURNER_EV_{idx}")
        obst_id = clean_fds_id(f"OBST_EV_{idx}")
        vent_id = clean_fds_id(f"VENT_BURNER_{idx}")

        # T-squared RAMP calculation
        t_delay = max(0.0, float(ev.ignition_delay_s))
        t_alpha = (preset.t_alpha_s[0] + preset.t_alpha_s[1]) / 2.0
        t_growth = t_alpha
        t_plateau = t_growth
        t_decay = t_growth

        lines.append(f"! Fire Curve Ramp: {ramp_id} (delay={t_delay}s, growth={t_growth}s)")
        if t_delay > 0:
            lines.append(f"&RAMP ID='{ramp_id}', T=0.0, F=0.0 /")
            lines.append(f"&RAMP ID='{ramp_id}', T={t_delay:.1f}, F=0.0 /")
        else:
            lines.append(f"&RAMP ID='{ramp_id}', T=0.0, F=0.0 /")

        for frac in (0.25, 0.50, 0.75, 1.0):
            t_curr = t_delay + frac * t_growth
            f_curr = frac * frac
            lines.append(f"&RAMP ID='{ramp_id}', T={t_curr:.1f}, F={f_curr:.4f} /")

        # Plateau
        t_plateau_end = t_delay + t_growth + t_plateau
        lines.append(f"&RAMP ID='{ramp_id}', T={t_plateau_end:.1f}, F=1.0000 /")

        # Decay
        t_decay_mid = t_plateau_end + 0.5 * t_decay
        lines.append(f"&RAMP ID='{ramp_id}', T={t_decay_mid:.1f}, F=0.5000 /")
        t_decay_end = t_plateau_end + t_decay
        lines.append(f"&RAMP ID='{ramp_id}', T={t_decay_end:.1f}, F=0.0000 /")

        # &SURF
        fuel_id = preset_fuel_ids[cfg["preset_key"]]
        lines.append(
            f"&SURF ID='{surf_id}', HRRPUA={hrrpua_kw_m2:.2f}, RAMP_Q='{ramp_id}', FUEL_ID='{fuel_id}' /"
        )

        # &OBST
        obst_xb = [xmin, xmax, ymin, ymax, zmin, zmax]
        lines.append(
            f"&OBST ID='{obst_id}', XB={format_xb(obst_xb)}, SURF_ID='INERT' /"
        )

        # &VENT (top surface of obstacle)
        vent_xb = [xmin, xmax, ymin, ymax, zmax, zmax]
        lines.append(
            f"&VENT ID='{vent_id}', XB={format_xb(vent_xb)}, SURF_ID='{surf_id}' /"
        )
        lines.append("")

    # 3. &DEVC for detection & suppression devices
    if normalized_devices:
        lines.append("! --- Fire Safety Devices ---")
        for dev in normalized_devices:
            dev_id = clean_fds_id(dev.id)
            lines.append(
                f"&DEVC ID='{dev_id}', QUANTITY='{dev.quantity}', "
                f"XYZ={format_xb(dev.position)}, SETPOINT={dev.setpoint} /"
            )
        lines.append("")

    # 4. &DEVC and &CTRL for door/opening events
    if normalized_opening_events:
        lines.append("! --- Opening & Boundary Controls ---")
        for ev_open in normalized_opening_events:
            clean_key = clean_fds_id(ev_open.entity_key)[:20].rstrip("._-")
            timer_devc_id = f"DEVC_{clean_key}_TIME"
            ctrl_id = clean_fds_id(f"CTRL_{clean_key}")

            lines.append(
                f"&DEVC ID='{timer_devc_id}', QUANTITY='TIME', SETPOINT={ev_open.event_time_s:.1f} /"
            )
            lines.append(
                f"&CTRL ID='{ctrl_id}', FUNCTION_TYPE='ANY', INPUT_ID='{timer_devc_id}' /"
            )

            # Check if mapping plan contains bounds for this entity
            decision = mapping_plan.get_decision(ev_open.entity_key)
            if decision and decision.representation_bounds:
                xb = decision.representation_bounds.to_xb()
                if ev_open.state == "OPEN":
                    lines.append(
                        f"&HOLE XB={format_xb(xb)}, CTRL_ID='{ctrl_id}' /"
                    )
                elif ev_open.state == "CLOSED":
                    lines.append(
                        f"&OBST XB={format_xb(xb)}, SURF_ID='INERT', CTRL_ID='{ctrl_id}' /"
                    )
            lines.append("")

    fds_fragment = "\n".join(lines)

    # Deterministic scenario ID based on full scenario fragment
    scenario_hash = hashlib.sha256(fds_fragment.encode("utf-8")).hexdigest()[:12]
    scenario_id = f"ev_scenario_{scenario_hash}"

    return ScenarioBundle(
        scenario_id=scenario_id,
        bundle_sha256=bundle_sha256,
        ev_library_version=EV_LIBRARY_VERSION,
        fds_fragment=fds_fragment,
        total_peak_hrr_mw=round(total_peak_hrr_mw, 6),
        ev_count=len(normalized_evs),
        ev_selections=normalized_evs,
        devices=normalized_devices,
        opening_events=normalized_opening_events,
    )
