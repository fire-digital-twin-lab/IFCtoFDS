"""Base protocol and outcome models for independent gate checkers."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol

from ..model import Finding, GateResult, ValidationContext


@dataclass
class CheckerOutcome:
    gate_name: str
    result: GateResult
    findings: List[Finding] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    element_statuses: Dict[str, str] = field(default_factory=dict)


class GateChecker(Protocol):
    name: str

    def check(self, context: ValidationContext) -> CheckerOutcome:
        ...
