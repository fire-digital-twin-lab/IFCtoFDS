"""Tests for EV fire scenario emitter (Task 3)."""

import pytest
import re

from ifc_to_fds.domain.mapping import MappingPlan
from ifc_to_fds.fire import (
    DeviceSelection,
    EVSelection,
    OpeningEvent,
    ScenarioBundle,
    emit_fire_scenario,
)


def _sample_mapping_plan() -> MappingPlan:
    return MappingPlan()


def _valid_bundle_hash() -> str:
    return "a" * 64


# --- Step 1 & Requirement Tests ---


def test_emitter_rejects_unverified_bundle():
    """Verify ValueError('MAPPING_VERIFIED') is raised when bundle is unverified or stale."""
    plan = _sample_mapping_plan()
    ev = EVSelection(preset_id="e-bike-lfp", position=(0.0, 0.0, 0.55))

    # Stale bundle hash
    with pytest.raises(ValueError, match="MAPPING_VERIFIED"):
        emit_fire_scenario(
            mapping_plan=plan,
            bundle_sha256="stale",
            ev_selections=[ev],
            opening_states={},
            verification_status="MAPPING_VERIFIED",
        )

    # Unverified status
    with pytest.raises(ValueError, match="MAPPING_VERIFIED"):
        emit_fire_scenario(
            mapping_plan=plan,
            bundle_sha256=_valid_bundle_hash(),
            ev_selections=[ev],
            opening_states={},
            verification_status="UNVERIFIED",
        )

    # Empty bundle hash
    with pytest.raises(ValueError, match="MAPPING_VERIFIED"):
        emit_fire_scenario(
            mapping_plan=plan,
            bundle_sha256="",
            ev_selections=[ev],
            opening_states={},
            verification_status="MAPPING_VERIFIED",
        )


def test_emitter_rejects_empty_ev_selections():
    """Verify ValueError is raised when ev_selections is empty."""
    plan = _sample_mapping_plan()
    with pytest.raises(ValueError, match="At least one EV selection is required"):
        emit_fire_scenario(
            mapping_plan=plan,
            bundle_sha256=_valid_bundle_hash(),
            ev_selections=[],
            verification_status="MAPPING_VERIFIED",
        )


def test_emit_single_ebike_fire_scenario():
    """Verify single e-bike emission produces REAC, RAMP, SURF, VENT, OBST in fds_fragment."""
    plan = _sample_mapping_plan()
    ev = EVSelection(preset_id="e-bike-lfp", position=(1.0, 2.0, 0.55))

    bundle = emit_fire_scenario(
        mapping_plan=plan,
        bundle_sha256=_valid_bundle_hash(),
        ev_selections=[ev],
        verification_status="MAPPING_VERIFIED",
    )

    assert isinstance(bundle, ScenarioBundle)
    assert bundle.ev_count == 1
    assert bundle.ev_library_version == "1.0.0"
    assert bundle.bundle_sha256 == _valid_bundle_hash()

    # Peak HRR within e-bike-lfp preset range: (0.02, 0.15) MW
    assert 0.02 <= bundle.total_peak_hrr_mw <= 0.15
    assert bundle.total_peak_hrr_mw == pytest.approx(0.085, rel=1e-3)

    frag = bundle.fds_fragment
    assert "&REAC" in frag
    assert "&RAMP" in frag
    assert "&SURF" in frag
    assert "&VENT" in frag
    assert "&OBST" in frag
    assert "SURF_ID='INERT'" in frag
    assert "HRRPUA=" in frag


def test_emit_auto_fire_scenario():
    """Verify auto-nmc combustion parameters and HRR peak within preset range."""
    plan = _sample_mapping_plan()
    ev = EVSelection(preset_id="auto-nmc", position=(5.0, 5.0, 0.75))

    bundle = emit_fire_scenario(
        mapping_plan=plan,
        bundle_sha256=_valid_bundle_hash(),
        ev_selections=[ev],
        verification_status="MAPPING_VERIFIED",
    )

    assert isinstance(bundle, ScenarioBundle)
    assert bundle.ev_count == 1
    # Auto NMC range: (2.0, 7.0) MW, midpoint = 4.5 MW
    assert 2.0 <= bundle.total_peak_hrr_mw <= 7.0
    assert bundle.total_peak_hrr_mw == pytest.approx(4.5, rel=1e-3)

    frag = bundle.fds_fragment
    # Combustion parameters: CO_YIELD = (0.05 + 0.20)/2 = 0.125, SOOT_YIELD = (0.08 + 0.20)/2 = 0.14
    assert re.search(r"CO_YIELD\s*=\s*0\.125", frag) is not None
    assert re.search(r"SOOT_YIELD\s*=\s*0\.14", frag) is not None

    # Check default dimensions for auto: 4.5 x 1.8 x 1.5
    # Center = (5.0, 5.0, 0.75) -> x=[2.75, 7.25], y=[4.1, 5.9], z=[0.0, 1.5]
    assert "2.75" in frag
    assert "7.25" in frag


def test_emit_cluster_ebikes_with_propagation_delays():
    """Verify multiple e-bikes with staggered ignition delays."""
    plan = _sample_mapping_plan()
    evs = [
        EVSelection(preset_id="e-bike-lfp", position=(0.0, 0.0, 0.55), ignition_delay_s=0.0),
        EVSelection(preset_id="e-bike-lfp", position=(0.0, 1.0, 0.55), ignition_delay_s=60.0),
        EVSelection(preset_id="e-bike-lfp", position=(0.0, 2.0, 0.55), ignition_delay_s=120.0),
    ]

    bundle = emit_fire_scenario(
        mapping_plan=plan,
        bundle_sha256=_valid_bundle_hash(),
        ev_selections=evs,
        verification_status="MAPPING_VERIFIED",
    )

    assert bundle.ev_count == 3
    # Total peak HRR is sum of 3 e-bikes: 3 * 0.085 = 0.255 MW
    assert bundle.total_peak_hrr_mw == pytest.approx(3 * 0.085, rel=1e-3)

    frag = bundle.fds_fragment
    # 3 OBSTs and 3 VENTs
    assert frag.count("&OBST") == 3
    assert frag.count("&VENT") == 3

    # Staggered delays present in RAMP definitions
    assert re.search(r"&RAMP.*T\s*=\s*60\.0", frag) is not None
    assert re.search(r"&RAMP.*T\s*=\s*120\.0", frag) is not None


def test_emit_scenario_with_devices_and_doors():
    """Verify DEVC/CTRL output and opening events."""
    plan = _sample_mapping_plan()
    ev = EVSelection(preset_id="e-bike-lfp", position=(1.0, 1.0, 0.55))
    devices = [
        DeviceSelection(
            id="SPK_01",
            device_type="SPRINKLER",
            position=(2.0, 2.0, 3.0),
            setpoint=68.0,
            quantity="SPRINKLER LINK TEMPERATURE",
        ),
        DeviceSelection(
            id="SMK_01",
            device_type="SMOKE_DETECTOR",
            position=(3.0, 3.0, 3.0),
            setpoint=0.03,
            quantity="CHAMBER OBSCURATION",
        ),
    ]
    opening_states = {
        "DOOR_MAIN": {"state": "OPEN", "event_time_s": 90.0},
        "DOOR_FIRE": {"state": "CLOSED", "eventTime": 180.0},
    }

    bundle = emit_fire_scenario(
        mapping_plan=plan,
        bundle_sha256=_valid_bundle_hash(),
        ev_selections=[ev],
        devices=devices,
        opening_states=opening_states,
        verification_status="MAPPING_VERIFIED",
    )

    assert len(bundle.devices) == 2
    assert len(bundle.opening_events) == 2

    frag = bundle.fds_fragment
    # Device namelists
    assert "SPK_01" in frag
    assert "SMK_01" in frag
    assert "SPRINKLER LINK TEMPERATURE" in frag
    assert "CHAMBER OBSCURATION" in frag

    # Door control DEVC and CTRL namelists
    assert "DOOR_MAIN" in frag
    assert "DOOR_FIRE" in frag
    assert "&CTRL" in frag


def test_custom_pack_and_peak_hrr():
    """Verify custom pack_kwh and peak_hrr_mw validation and usage."""
    plan = _sample_mapping_plan()

    # Valid custom values within preset range
    ev_custom = EVSelection(
        preset_id="auto-nmc",
        position=(0.0, 0.0, 0.75),
        pack_kwh=80.0,
        peak_hrr_mw=5.5,
    )
    bundle = emit_fire_scenario(
        mapping_plan=plan,
        bundle_sha256=_valid_bundle_hash(),
        ev_selections=[ev_custom],
        verification_status="MAPPING_VERIFIED",
    )
    assert bundle.total_peak_hrr_mw == pytest.approx(5.5)

    # Invalid custom peak HRR out of range (auto-nmc range is 2.0 to 7.0)
    ev_out_of_range = EVSelection(
        preset_id="auto-nmc",
        position=(0.0, 0.0, 0.75),
        peak_hrr_mw=15.0,
    )
    with pytest.raises(ValueError, match="out of.*range"):
        emit_fire_scenario(
            mapping_plan=plan,
            bundle_sha256=_valid_bundle_hash(),
            ev_selections=[ev_out_of_range],
            verification_status="MAPPING_VERIFIED",
        )
