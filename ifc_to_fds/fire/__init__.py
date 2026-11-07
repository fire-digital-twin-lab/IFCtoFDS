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
from ifc_to_fds.fire.vehicle_collision import VehicleCollisionAssessment
from ifc_to_fds.fire.vehicle_geometry import BatteryPack, VehicleGeometry
from ifc_to_fds.fire.mesh_plan import (
    LocalMeshPlanRequest,
    MeshRegion,
    ResolvedLocalMeshPlan,
)
from ifc_to_fds.fire.mesh_metrics import calculate_d_star


def check_mesh_resolution(*args, **kwargs):
    """Lazy compatibility facade avoiding a fire-domain/validation import cycle."""

    from ifc_to_fds.validation.checkers.mesh_resolution import (
        check_mesh_resolution as implementation,
    )

    return implementation(*args, **kwargs)


def __getattr__(name):
    if name == "MeshResolutionChecker":
        from ifc_to_fds.validation.checkers.mesh_resolution import MeshResolutionChecker

        return MeshResolutionChecker
    raise AttributeError(name)

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
    "BatteryPack",
    "VehicleGeometry",
    "VehicleCollisionAssessment",
    "LocalMeshPlanRequest",
    "MeshRegion",
    "ResolvedLocalMeshPlan",
    "MeshResolutionChecker",
    "calculate_d_star",
    "check_mesh_resolution",
]
