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
from ifc_to_fds.fire.grid_sensitivity import (
    ApplicationGridStudyReadiness,
    ExecutedGridSensitivityStudyEvidence,
    GridSensitivityCaseExecutionEvidence,
    GridSensitivityCaseResult,
    GridSensitivityObservableRequest,
    GridSensitivityObservation,
    GridSensitivityPlanRequest,
    GridSensitivityStudyEvidence,
    ResolvedGridSensitivityPlan,
    analyze_grid_sensitivity,
    assess_application_grid_study_readiness,
    execute_grid_sensitivity_study,
    require_application_grid_study_ready,
    render_grid_sensitivity_cases,
    resolve_grid_sensitivity_plan,
)
from ifc_to_fds.fire.mesh_gate import (
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
    "BatteryPack",
    "VehicleGeometry",
    "VehicleCollisionAssessment",
    "LocalMeshPlanRequest",
    "MeshRegion",
    "ResolvedLocalMeshPlan",
    "ApplicationGridStudyReadiness",
    "ExecutedGridSensitivityStudyEvidence",
    "GridSensitivityCaseExecutionEvidence",
    "GridSensitivityCaseResult",
    "GridSensitivityObservableRequest",
    "GridSensitivityObservation",
    "GridSensitivityPlanRequest",
    "GridSensitivityStudyEvidence",
    "ResolvedGridSensitivityPlan",
    "analyze_grid_sensitivity",
    "assess_application_grid_study_readiness",
    "execute_grid_sensitivity_study",
    "require_application_grid_study_ready",
    "render_grid_sensitivity_cases",
    "resolve_grid_sensitivity_plan",
    "MeshResolutionChecker",
    "calculate_d_star",
    "check_mesh_resolution",
]
