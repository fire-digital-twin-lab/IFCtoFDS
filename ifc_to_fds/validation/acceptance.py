"""Explicit evidence gates; absence of findings is not a pass (Compatibility Facade).

Re-exports validation domain models from ifc_to_fds.domain.validation.
"""

from ifc_to_fds.domain.validation import (
    AcceptanceReport,
    AcceptanceStatus,
    AcceptanceVerdict,
    AuditConfig,
    Finding,
    GateResult,
    GateStatus,
    Severity,
    ValidationContext,
)

__all__ = [
    "Severity",
    "AcceptanceStatus",
    "AcceptanceVerdict",
    "GateStatus",
    "GateResult",
    "AuditConfig",
    "Finding",
    "ValidationContext",
    "AcceptanceReport",
]
