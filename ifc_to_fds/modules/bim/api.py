"""Public API of the bim module; only named exports are supported."""

from ifc_to_fds.modules._exports import resolve

_EXPORTS = {'IfcOpenShellReader': ('ifc_to_fds.modules.bim.infrastructure.ifc.reader', 'IfcOpenShellReader'),
 'classify_mep_element': ('ifc_to_fds.modules.bim.infrastructure.ifc.mep.classifier', 'classify_mep_element'),
 'compute_file_sha256': ('ifc_to_fds.modules.bim.infrastructure.ifc.inventory', 'compute_file_sha256'),
 'extract_inventory': ('ifc_to_fds.modules.bim.infrastructure.ifc.inventory', 'extract_inventory'),
 'extract_mep_graph': ('ifc_to_fds.modules.bim.infrastructure.ifc.mep.graph_reader', 'extract_mep_graph'),
 'extract_placement': ('ifc_to_fds.modules.bim.infrastructure.ifc.placement', 'extract_placement'),
 'get_length_unit_scale': ('ifc_to_fds.modules.bim.infrastructure.ifc.units', 'get_length_unit_scale'),
 'graph_differences': ('ifc_to_fds.modules.bim.domain.mep_comparison', 'graph_differences'),
 'load_sources': ('ifc_to_fds.modules.bim.infrastructure.ifc.source_loader', 'load_sources'),
 'preview_model': ('ifc_to_fds.modules.bim.infrastructure.ifc.preview', 'preview_model')}

__all__ = list(_EXPORTS)


def __getattr__(name):
    return resolve(_EXPORTS, name)
