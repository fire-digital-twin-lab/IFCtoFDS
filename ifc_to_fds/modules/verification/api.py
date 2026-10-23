"""Public API of the verification module; only named exports are supported."""

from ifc_to_fds.modules._exports import resolve

_EXPORTS = {'IndependentValidationEngine': ('ifc_to_fds.modules.verification.infrastructure.engine_adapter', 'IndependentValidationEngine'),
 'verification_capabilities': ('ifc_to_fds.modules.verification.application.capabilities', 'verification_capabilities'),
 'summarize_handoff': ('ifc_to_fds.modules.verification.application.handoff', 'summarize_handoff'),
 'prepare_geometry_run': ('ifc_to_fds.modules.verification.application.geometry_run', 'prepare_geometry_run'),
 'validate_editor_evidence': ('ifc_to_fds.modules.verification.application.editor_evidence', 'validate_editor_evidence'),
 'solver_gates': ('ifc_to_fds.modules.verification.infrastructure.fds.solver_process', 'solver_gates'),
 'compare_roundtrip_geometry': ('ifc_to_fds.modules.verification.application.roundtrip', 'compare_roundtrip_geometry'),
 "assess_saved_evidence": ("ifc_to_fds.modules.verification.application.saved_evidence", "assess_saved_evidence"),
 'ValidationRunner': ('ifc_to_fds.modules.verification.application.runner', 'ValidationRunner'),
 'calculate_bbox_iou': ('ifc_to_fds.modules.geometry.api', 'calculate_bbox_iou'),
 'compare_solids': ('ifc_to_fds.modules.geometry.api', 'compare_solids'),
 'finalize_boundary': ('ifc_to_fds.modules.verification.application.boundary_acceptance', 'finalize_boundary'),
 'passage_metrics': ('ifc_to_fds.modules.geometry.api', 'passage_metrics'),
 'run_independent_validation': ('ifc_to_fds.modules.verification.application.engine',
                                'run_independent_validation'),
 'verify_opening_retention': ('ifc_to_fds.modules.geometry.api', 'verify_opening_retention')}

__all__ = list(_EXPORTS)


def __getattr__(name):
    return resolve(_EXPORTS, name)
