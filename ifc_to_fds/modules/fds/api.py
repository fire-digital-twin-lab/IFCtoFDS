"""Public API of the fds module; only named exports are supported."""

from ifc_to_fds.modules._exports import resolve

_EXPORTS = {'FdsExporter': ('ifc_to_fds.modules.fds.infrastructure.exporter', 'FdsExporter'),
 'FDSRecord': ('ifc_to_fds.modules.fds.parsing.namelist', 'FDSRecord'),
 'MappingManifest': ('ifc_to_fds.domain.mapping', 'MappingManifest'),
 'SerializationResult': ('ifc_to_fds.modules.fds.application.serializer', 'SerializationResult'),
 'build_manifest': ('ifc_to_fds.modules.fds.application.manifest_builder', 'build_manifest'),
 'parse_fds': ('ifc_to_fds.modules.fds.parsing.namelist', 'parse_fds'),
 'serialize_fds': ('ifc_to_fds.modules.fds.application.serializer', 'serialize_fds')}

__all__ = list(_EXPORTS)


def __getattr__(name):
    return resolve(_EXPORTS, name)
