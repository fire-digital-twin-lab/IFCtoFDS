"""Independent validation engine, metrics, and acceptance gate."""

from ifc_to_fds.domain.validation.model import ValidationContext
from .acceptance import AcceptanceReport, AcceptanceStatus, Finding, Severity
from .engine import run_independent_validation
from .metrics import calculate_bbox_iou, verify_opening_retention
from .parser import parse_fds

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
