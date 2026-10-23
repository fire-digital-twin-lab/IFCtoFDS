"""Independent validation engine, metrics, and acceptance gate."""

from ifc_to_fds.domain.validation.model import ValidationContext
from .acceptance import AcceptanceReport, AcceptanceStatus, Finding, Severity
from ifc_to_fds.modules.verification.application.engine import run_independent_validation
from ifc_to_fds.modules.geometry.algorithms.metrics import calculate_bbox_iou, verify_opening_retention
from ifc_to_fds.modules.fds.parsing.namelist import parse_fds

ValidationContext.register_parser(parse_fds)

__all__ = [
    "AcceptanceReport",
    "AcceptanceStatus",
    "Finding",
    "Severity",
    "calculate_bbox_iou",
    "run_independent_validation",
    "verify_opening_retention",
]
