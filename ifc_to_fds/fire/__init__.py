"""EV fire scenario physics: preset library and scenario emission."""

from ifc_to_fds.fire.ev_library import (
    EVPreset,
    EV_LIBRARY_VERSION,
    Citation,
    SpeciesYields,
    library_digest,
    library_dir,
    list_ev_presets,
    load_ev_preset,
)
from ifc_to_fds.fire.scenario_emitter import (
    DeviceSelection,
    EVSelection,
    OpeningEvent,
    ScenarioBundle,
    emit_fire_scenario,
)
from ifc_to_fds.validation.checkers.mesh_resolution import (
    MeshResolutionChecker,
    calculate_d_star,
    check_mesh_resolution,
)

__all__ = [
    "EVPreset",
    "EV_LIBRARY_VERSION",
    "Citation",
    "SpeciesYields",
    "library_digest",
    "library_dir",
    "list_ev_presets",
    "load_ev_preset",
    "DeviceSelection",
    "EVSelection",
    "OpeningEvent",
    "ScenarioBundle",
    "emit_fire_scenario",
    "MeshResolutionChecker",
    "calculate_d_star",
    "check_mesh_resolution",
]
