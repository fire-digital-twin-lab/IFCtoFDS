"""Public API of the reference module; only named exports are supported."""

from ifc_to_fds.modules._exports import resolve

_EXPORTS = {"registered_cases": ("ifc_to_fds.modules.reference.infrastructure.registry", "registered_cases"), "research_context": ("ifc_to_fds.modules.reference.infrastructure.registry", "research_context"), 'FILES': ('ifc_to_fds.modules.reference.infrastructure.filesystem_repository', 'FILES'),
 'FilesystemReferenceRepository': ('ifc_to_fds.modules.reference.infrastructure.filesystem_repository',
                                   'FilesystemReferenceRepository'),
 'bundle_digest': ('ifc_to_fds.modules.reference.infrastructure.bundle_io', 'bundle_digest'),
 'create_candidate': ('ifc_to_fds.modules.reference.infrastructure.bundle_io', 'create_candidate'),
 'golden_gate': ('ifc_to_fds.modules.reference.application.parity', 'golden_gate'),
 'inspect_case': ('ifc_to_fds.modules.reference.infrastructure.bundle_io', 'inspect_case'),
 'resolve_case': ('ifc_to_fds.modules.reference.infrastructure.bundle_io', 'resolve_case'),
 'resolve_sources': ('ifc_to_fds.modules.reference.infrastructure.bundle_io', 'resolve_sources'),
 'serialized_geometry': ('ifc_to_fds.modules.reference.application.projections', 'serialized_geometry'),
 'source_signature': ('ifc_to_fds.modules.reference.application.projections', 'source_signature')}

__all__ = list(_EXPORTS)


def __getattr__(name):
    return resolve(_EXPORTS, name)
