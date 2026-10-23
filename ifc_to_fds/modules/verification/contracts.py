"""Evidence and acceptance contracts; an unexecuted gate is never a passing gate."""

from ifc_to_fds.domain.validation import AcceptanceReport, AuditConfig, Finding, GateResult, GateStatus, Severity

__all__ = ["AcceptanceReport", "AuditConfig", "Finding", "GateResult", "GateStatus", "Severity"]
