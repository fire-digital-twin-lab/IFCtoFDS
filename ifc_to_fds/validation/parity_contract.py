"""Fail-closed comparison contract for legacy-engine versus modular-runner audits.

This comparator never executes a validator. It only evaluates reports supplied
by a caller, so an unverified modular run cannot replace the authoritative
independent audit or trigger an extra solver invocation in production.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from ifc_to_fds.domain.validation.model import AcceptanceReport

# Diagnostic wall-clock measurements are not scientific equivalence claims.
# All other metric/evidence differences are reported, not silently tolerated.
NONDETERMINISTIC_METRICS = frozenset({"solver_s", "stage_timings"})


@dataclass(frozen=True)
class ParityDifference:
    path: str
    authoritative: Any
    candidate: Any


@dataclass(frozen=True)
class ValidationParity:
    differences: tuple[ParityDifference, ...]

    @property
    def equivalent(self) -> bool:
        return not self.differences

    def assert_equivalent(self) -> None:
        if self.differences:
            preview = "; ".join(
                f"{item.path}: engine={item.authoritative!r}; runner={item.candidate!r}"
                for item in self.differences[:8]
            )
            raise AssertionError(
                f"Validation reports are not semantically equivalent "
                f"({len(self.differences)} differences): {preview}"
            )


def _compare(path: str, expected: Any, actual: Any, output: list[ParityDifference]) -> None:
    """Compare mappings recursively and never ignore absent or additional keys."""
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        for key in sorted(set(expected) | set(actual), key=str):
            present_expected = key in expected
            present_actual = key in actual
            subpath = f"{path}.{key}"
            if not present_expected or not present_actual:
                output.append(
                    ParityDifference(
                        subpath,
                        expected[key] if present_expected else "<MISSING>",
                        actual[key] if present_actual else "<MISSING>",
                    )
                )
            else:
                _compare(subpath, expected[key], actual[key], output)
    elif expected != actual:
        output.append(ParityDifference(path, expected, actual))


def compare_validation_reports(
    authoritative: AcceptanceReport,
    candidate: AcceptanceReport,
    *,
    compare_details: bool = False,
) -> ValidationParity:
    """Identify parity failures without silently promoting the candidate.

    Baseline parity checks verdicts, gate status/required fields, entity states
    and counts. Detailed mode adds coverage, gate evidence and reasons,
    finding payloads and deterministic metrics, which may expose existing
    differences that must be investigated before any engine migration.
    """
    differences: list[ParityDifference] = []
    for name in ("status", "mapping_status", "simulation_status"):
        _compare(name, getattr(authoritative, name), getattr(candidate, name), differences)

    engine_gates = authoritative.gates
    runner_gates = candidate.gates
    for gate in sorted(set(engine_gates) | set(runner_gates)):
        if gate not in engine_gates or gate not in runner_gates:
            differences.append(
                ParityDifference(
                    f"gates.{gate}",
                    engine_gates[gate].model_dump(mode="json") if gate in engine_gates else "<MISSING>",
                    runner_gates[gate].model_dump(mode="json") if gate in runner_gates else "<MISSING>",
                )
            )
            continue
        for field in ("status", "required"):
            _compare(
                f"gates.{gate}.{field}",
                getattr(engine_gates[gate], field),
                getattr(runner_gates[gate], field),
                differences,
            )
        if compare_details:
            for field in ("reason", "reason_code", "evidence"):
                _compare(
                    f"gates.{gate}.{field}",
                    getattr(engine_gates[gate], field),
                    getattr(runner_gates[gate], field),
                    differences,
                )

    for name in (
        "element_statuses",
        "total_elements_checked",
        "matched_count",
        "missing_count",
        "deviated_count",
        "excluded_count",
        "semantic_only_count",
    ):
        _compare(
            name, getattr(authoritative, name), getattr(candidate, name), differences
        )
    if compare_details:
        for name in ("findings", "coverage"):
            left, right = getattr(authoritative, name), getattr(candidate, name)
            if name == "findings":
                left = [finding.model_dump(mode="json") for finding in left]
                right = [finding.model_dump(mode="json") for finding in right]
            _compare(name, left, right, differences)
        _compare(
            "metrics",
            {key: val for key, val in authoritative.metrics.items() if key not in NONDETERMINISTIC_METRICS},
            {key: val for key, val in candidate.metrics.items() if key not in NONDETERMINISTIC_METRICS},
            differences,
        )
    return ValidationParity(tuple(differences))
