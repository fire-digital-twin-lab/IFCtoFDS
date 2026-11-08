"""Validate P4c2 DEVC metadata and extract scalar solver observables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ifc_to_fds.validation.parser import FDSRecord, parse_fds

from .grid_sensitivity_execution_models import GridSensitivityObservableRequest
from .grid_sensitivity_models import GridSensitivityObservation
from .grid_sensitivity_outputs import DeviceTimeSeries, load_fds_device_series


def _record_descriptor_sha256(record: FDSRecord) -> str:
    payload = json.dumps(
        {"kind": record.kind, "values": record.values},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _single_value(record: FDSRecord, field: str) -> Any | None:
    values = record.values.get(field, [])
    if not values:
        return None
    if len(values) != 1:
        raise ValueError(f"{record.kind} {record.id}: {field} must have one value")
    return values[0]


def scenario_observable_metadata(
    scenario_fds: str,
    requests: list[GridSensitivityObservableRequest],
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Validate requested point DEVC metadata before any solver process starts."""

    parsed = parse_fds(scenario_fds)
    if parsed.errors or parsed.unsupported:
        raise ValueError(
            "P4c2 requires parser-clean scientific FDS before solver execution"
        )

    heads = [record for record in parsed.records if record.kind == "HEAD"]
    if len(heads) != 1:
        raise ValueError("P4c2 requires exactly one FDS HEAD record")
    chid = _single_value(heads[0], "CHID")
    if not isinstance(chid, str) or not chid.strip():
        raise ValueError("P4c2 requires a non-empty HEAD.CHID")
    chid = chid.strip()

    metric_ids = [request.metric_id for request in requests]
    device_ids = [request.device_id for request in requests]
    if not requests:
        raise ValueError("P4c2 requires at least one explicit DEVC observable")
    if len(metric_ids) != len(set(metric_ids)):
        raise ValueError("P4c2 observable metric_id values must be unique")
    if len(device_ids) != len(set(device_ids)):
        raise ValueError("P4c2 observable device_id values must be unique")

    metadata: dict[str, dict[str, Any]] = {}
    for request in requests:
        matches = [
            record
            for record in parsed.records
            if record.kind == "DEVC" and record.id == request.device_id
        ]
        if len(matches) != 1:
            raise ValueError(
                f"P4c2 requires exactly one DEVC with ID {request.device_id!r}"
            )
        record = matches[0]
        quantity = _single_value(record, "QUANTITY")
        if not isinstance(quantity, str) or not quantity.strip():
            raise ValueError(
                "P4c2 supports only DEVC records with explicit QUANTITY: "
                f"{request.device_id}"
            )
        if quantity.strip().upper() != request.expected_quantity.strip().upper():
            raise ValueError(
                f"DEVC {request.device_id!r} quantity {quantity!r} differs from "
                f"expected {request.expected_quantity!r}"
            )

        xyz = record.values.get("XYZ", [])
        if len(xyz) != 3:
            raise ValueError(
                "P4c2 currently supports only point DEVC XYZ observables: "
                f"{request.device_id}"
            )
        location = tuple(float(value) for value in xyz)

        declared_units = _single_value(record, "UNITS")
        if (
            declared_units is not None
            and str(declared_units).strip() != request.expected_unit.strip()
        ):
            raise ValueError(
                f"DEVC {request.device_id!r} declared UNITS {declared_units!r} "
                f"differs from expected {request.expected_unit!r}"
            )

        metadata[request.metric_id] = {
            "device_id": request.device_id,
            "quantity": quantity.strip(),
            "location_m": location,
            "descriptor_sha256": _record_descriptor_sha256(record),
        }
    return chid, metadata


def _aggregate(
    series: DeviceTimeSeries,
    request: GridSensitivityObservableRequest,
) -> float:
    samples = list(zip(series.times_s, series.values, strict=True))
    if request.time_window_s is not None:
        start, stop = request.time_window_s
        samples = [
            (time_s, value)
            for time_s, value in samples
            if start <= time_s <= stop
        ]
    if not samples:
        raise ValueError(
            f"No FDS DEVC samples remain for metric {request.metric_id!r} "
            "inside the requested time window"
        )

    values = [value for _, value in samples]
    if request.aggregation == "MAX":
        return max(values)
    if request.aggregation == "MIN":
        return min(values)
    if request.aggregation == "FINAL":
        return samples[-1][1]
    raise ValueError(f"Unsupported P4c2 aggregation: {request.aggregation}")


def observations_from_solver_output(
    directory: Path,
    chid: str,
    requests: list[GridSensitivityObservableRequest],
    metadata: dict[str, dict[str, Any]],
) -> list[GridSensitivityObservation]:
    """Build comparable observations only from requested, verified DEVC columns."""

    series_by_id = load_fds_device_series(directory, chid)
    observations: list[GridSensitivityObservation] = []
    for request in requests:
        series = series_by_id.get(request.device_id)
        if series is None:
            raise ValueError(
                "FDS DEVC output does not contain requested device "
                f"{request.device_id!r}"
            )
        if series.unit != request.expected_unit.strip():
            raise ValueError(
                f"FDS DEVC unit {series.unit!r} for {request.device_id!r} "
                f"differs from expected {request.expected_unit!r}"
            )
        descriptor = metadata[request.metric_id]
        observations.append(
            GridSensitivityObservation(
                metric_id=request.metric_id,
                quantity=descriptor["quantity"],
                unit=series.unit,
                value=_aggregate(series, request),
                aggregation=request.aggregation,
                location_m=descriptor["location_m"],
                time_window_s=request.time_window_s,
                source_artifact=series.source_artifact,
                source_sha256=series.source_sha256,
                source_device_id=descriptor["device_id"],
                source_descriptor_sha256=descriptor["descriptor_sha256"],
            )
        )
    return observations
