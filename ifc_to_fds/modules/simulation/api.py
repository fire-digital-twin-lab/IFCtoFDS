"""Public API of the simulation module; only named exports are supported."""

from ifc_to_fds.modules._exports import resolve

_EXPORTS = {'EXACT_POLICY': ('ifc_to_fds.modules.simulation.application.boundary_policy', 'EXACT_POLICY'),
 'FIXTURES': ('ifc_to_fds.modules.simulation.application.boundary_policy', 'FIXTURES'),
 'POLICY': ('ifc_to_fds.modules.simulation.application.boundary_policy', 'POLICY'),
 'SpatialScope': ('ifc_to_fds.domain.scope', 'SpatialScope'),
 'VERSION': ('ifc_to_fds.modules.simulation.application.boundary_policy', 'VERSION'),
 'adapter_digest': ('ifc_to_fds.modules.simulation.infrastructure.implementation_digest', 'adapter_digest'),
 'apply_spatial_scope': ('ifc_to_fds.modules.simulation.application.spatial_scope', 'apply_spatial_scope'),
 'determine_element_strategy': ('ifc_to_fds.modules.simulation.application.mapping_policy',
                                'determine_element_strategy'),
 'fixture_cases': ('ifc_to_fds.modules.simulation.domain.boundary_cases', 'fixture_cases'),
 'fixture_text': ('ifc_to_fds.modules.simulation.domain.boundary_cases', 'fixture_text'),
 'plan_mapping': ('ifc_to_fds.modules.simulation.application.mapping_policy', 'plan_mapping'),
 'planned_model': ('ifc_to_fds.modules.simulation.application.plan_validation', 'planned_model'),
 'target_mesh': ('ifc_to_fds.modules.simulation.application.boundary_policy', 'target_mesh'),
 'validate_decisions': ('ifc_to_fds.modules.simulation.application.mapping_policy', 'validate_decisions')}

__all__ = list(_EXPORTS)


def __getattr__(name):
    return resolve(_EXPORTS, name)
