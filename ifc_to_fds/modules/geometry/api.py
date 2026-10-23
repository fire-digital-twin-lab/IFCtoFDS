"""Public API of the geometry module; only named exports are supported."""

from ifc_to_fds.modules._exports import resolve

_EXPORTS = {'calculate_bbox_iou': ('ifc_to_fds.modules.geometry.algorithms.metrics', 'calculate_bbox_iou'), 'verify_opening_retention': ('ifc_to_fds.modules.geometry.algorithms.metrics', 'verify_opening_retention'), 'read_preview': ('ifc_to_fds.modules.geometry.infrastructure.preview_cache', 'read_preview'),
 'save_preview': ('ifc_to_fds.modules.geometry.infrastructure.preview_cache', 'save_preview'),
 'DiskPackage': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'DiskPackage'),
 'SolidCandidateIndex': ('ifc_to_fds.modules.geometry.algorithms.metrics', 'SolidCandidateIndex'),
 'archive_package': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'archive_package'),
 'as_trimesh': ('ifc_to_fds.modules.geometry.algorithms.mesh', 'as_trimesh'),
 'audit_package': ('ifc_to_fds.modules.geometry.application.package_service', 'audit_package'),
 'bounds_for_vertices': ('ifc_to_fds.modules.geometry.algorithms.mesh', 'bounds_for_vertices'),
 'box_mesh': ('ifc_to_fds.modules.geometry.algorithms.mesh', 'box_mesh'),
 'build_package': ('ifc_to_fds.modules.geometry.application.package_service', 'build_package'),
 'cached_geometry': ('ifc_to_fds.modules.geometry.infrastructure.cache', 'cached_geometry'),
 'compare_solids': ('ifc_to_fds.modules.geometry.algorithms.metrics', 'compare_solids'),
 'copy_package': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'copy_package'),
 'create_geom_settings': ('ifc_to_fds.modules.geometry.infrastructure.ifcopenshell.extraction', 'create_geom_settings'),
 'digest': ('ifc_to_fds.modules.geometry.application.package_service', 'digest'),
 'extract_element_geometry': ('ifc_to_fds.modules.geometry.infrastructure.ifcopenshell.extraction', 'extract_element_geometry'),
 'file_hash': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'file_hash'),
 'inspect_mesh_quality': ('ifc_to_fds.modules.geometry.algorithms.mesh', 'inspect_mesh_quality'),
 'intersects_box': ('ifc_to_fds.modules.geometry.algorithms.mesh', 'intersects_box'),
 'is_axis_aligned_box': ('ifc_to_fds.modules.geometry.algorithms.mesh', 'is_axis_aligned_box'),
 'mesh_evidence_scope': ('ifc_to_fds.modules.geometry.algorithms.mesh', 'mesh_evidence_scope'),
 'mesh_from_geometry': ('ifc_to_fds.modules.geometry.infrastructure.ifcopenshell.extraction', 'mesh_from_geometry'),
 'metrics_pass': ('ifc_to_fds.modules.geometry.application.package_service', 'metrics_pass'),
 'opening_residual': ('ifc_to_fds.modules.geometry.algorithms.metrics', 'opening_residual'),
 'passage_metrics': ('ifc_to_fds.modules.geometry.algorithms.metrics', 'passage_metrics'),
 'payload_dir': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'payload_dir'),
 'process_model_geometry': ('ifc_to_fds.modules.geometry.infrastructure.ifcopenshell.extraction', 'process_model_geometry'),
 'process_reference_geometry': ('ifc_to_fds.modules.geometry.infrastructure.ifcopenshell.extraction', 'process_reference_geometry'),
 'read_package': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'read_package'),
 'restore_package': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'restore_package'),
 'seal': ('ifc_to_fds.modules.geometry.application.package_service', 'seal'),
 'solid_boolean': ('ifc_to_fds.modules.geometry.algorithms.boolean', 'solid_boolean'),
 'store_mesh': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'store_mesh'),
 'valid_solid': ('ifc_to_fds.modules.geometry.algorithms.mesh', 'valid_solid'),
 'verify_package': ('ifc_to_fds.modules.geometry.application.package_service', 'verify_package'),
 'write_package': ('ifc_to_fds.modules.geometry.infrastructure.payload_store', 'write_package')}

__all__ = list(_EXPORTS)


def __getattr__(name):
    return resolve(_EXPORTS, name)
