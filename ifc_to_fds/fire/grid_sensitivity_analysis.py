"""Descriptive P4c grid-sensitivity analysis without invented thresholds."""

from __future__ import annotations

from .grid_sensitivity_models import (
    GridSensitivityCaseResult,
    GridSensitivityStudyEvidence,
    MetricSensitivityEvidence,
)


_LEVELS = ("COARSE", "MEDIUM", "FINE")


def _observation_map(case: GridSensitivityCaseResult):
    return {observation.metric_id: observation for observation in case.observations}


def _descriptor(observation):
    return (
        observation.quantity,
        observation.unit,
        observation.aggregation,
        observation.location_m,
        observation.time_window_s,
        observation.source_device_id,
        observation.source_descriptor_sha256,
    )


def _relative_to_finer(coarser: float, finer: float) -> float | None:
    if finer == 0.0:
        return None
    return abs(finer - coarser) / abs(finer)


def _trend(coarse: float, medium: float, fine: float) -> str:
    first = medium - coarse
    second = fine - medium
    if first == 0.0 and second == 0.0:
        return "FLAT"
    if first * second > 0.0:
        return "MONOTONIC"
    if first * second < 0.0:
        return "OSCILLATORY"
    return "PLATEAU_OR_UNRESOLVED"


def _change_trend(coarse: float, medium: float, fine: float) -> str:
    first = abs(medium - coarse)
    second = abs(fine - medium)
    if second < first:
        return "DECREASING_CHANGE"
    if second > first:
        return "INCREASING_CHANGE"
    return "UNCHANGED_CHANGE_MAGNITUDE"


def analyze_grid_sensitivity(
    cases: list[GridSensitivityCaseResult],
) -> GridSensitivityStudyEvidence:
    """Compare three grids but never issue scientific convergence PASS."""

    if len(cases) != 3 or [case.level for case in cases] != list(_LEVELS):
        raise ValueError("Grid-sensitivity results must be ordered COARSE/MEDIUM/FINE")

    ratios = [case.refinement_ratio for case in cases]
    if not (ratios[0] < ratios[1] < ratios[2]):
        raise ValueError("Result refinement ratios must be strictly increasing")
    local_dx = [case.local_dx_m for case in cases]
    if not (local_dx[0] > local_dx[1] > local_dx[2]):
        raise ValueError("Result local dx must strictly decrease toward FINE")

    invariant_hashes = {case.scenario_invariant_sha256 for case in cases}
    if len(invariant_hashes) != 1:
        raise ValueError(
            "Grid-sensitivity cases differ outside the declared mesh refinement scope"
        )

    maps = [_observation_map(case) for case in cases]
    metric_ids = set(maps[0])
    if not metric_ids or any(set(item) != metric_ids for item in maps[1:]):
        raise ValueError("Grid-sensitivity cases must contain the same metric_id set")

    metrics: list[MetricSensitivityEvidence] = []
    for metric_id in sorted(metric_ids):
        observations = [item[metric_id] for item in maps]
        if len({_descriptor(observation) for observation in observations}) != 1:
            raise ValueError(
                f"Observable metadata differs across grids for metric '{metric_id}'"
            )
        coarse, medium, fine = [observation.value for observation in observations]
        first_delta = medium - coarse
        second_delta = fine - medium
        metrics.append(
            MetricSensitivityEvidence(
                metric_id=metric_id,
                quantity=observations[0].quantity,
                unit=observations[0].unit,
                aggregation=observations[0].aggregation,
                coarse_value=coarse,
                medium_value=medium,
                fine_value=fine,
                coarse_to_medium_delta=first_delta,
                medium_to_fine_delta=second_delta,
                coarse_to_medium_abs_delta=abs(first_delta),
                medium_to_fine_abs_delta=abs(second_delta),
                coarse_to_medium_relative_to_finer=_relative_to_finer(
                    coarse, medium
                ),
                medium_to_fine_relative_to_finer=_relative_to_finer(medium, fine),
                trend=_trend(coarse, medium, fine),
                change_trend=_change_trend(coarse, medium, fine),
            )
        )

    return GridSensitivityStudyEvidence(
        reason=(
            "Three comparable mesh cases were analyzed descriptively, but no "
            "reviewed acceptance policy or numerical-uncertainty model is defined. "
            "Pairwise changes cannot establish mesh independence by themselves."
        ),
        scenario_invariant_sha256=cases[0].scenario_invariant_sha256,
        cases=cases,
        metrics=metrics,
    )
