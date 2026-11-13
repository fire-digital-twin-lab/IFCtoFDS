"""Strict FDS DEVC CSV ingestion for executed P4c2 studies."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re


@dataclass(frozen=True)
class DeviceTimeSeries:
    """One FDS device time series with artifact provenance."""

    device_id: str
    unit: str
    times_s: tuple[float, ...]
    values: tuple[float, ...]
    source_artifact: str
    source_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _numeric(value: str, *, artifact: str, row: int, column: str) -> float:
    try:
        number = float(value.strip())
    except ValueError as exc:
        raise ValueError(
            f"Non-numeric FDS DEVC value in {artifact} row {row}, column {column!r}"
        ) from exc
    if not math.isfinite(number):
        raise ValueError(
            f"Non-finite FDS DEVC value in {artifact} row {row}, column {column!r}"
        )
    return number


def _read_devc_file(path: Path) -> dict[str, DeviceTimeSeries]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = [
            [cell.strip() for cell in row]
            for row in csv.reader(stream)
            if row and any(cell.strip() for cell in row)
        ]
    if len(rows) < 3:
        raise ValueError(f"FDS DEVC artifact has no data rows: {path.name}")

    units, labels = rows[0], rows[1]
    if len(units) != len(labels) or len(labels) < 2:
        raise ValueError(f"FDS DEVC header width mismatch: {path.name}")
    if units[0] != "s" or labels[0] != "Time":
        raise ValueError(
            f"FDS DEVC header must start with units 's' and label 'Time': {path.name}"
        )
    if any(not label for label in labels[1:]):
        raise ValueError(f"FDS DEVC contains empty device ID: {path.name}")
    if len(labels[1:]) != len(set(labels[1:])):
        raise ValueError(f"FDS DEVC contains duplicate device IDs: {path.name}")

    times: list[float] = []
    columns: list[list[float]] = [[] for _ in labels[1:]]
    for row_number, row in enumerate(rows[2:], start=3):
        if len(row) != len(labels):
            raise ValueError(
                f"FDS DEVC data width mismatch in {path.name} row {row_number}"
            )
        time_s = _numeric(
            row[0], artifact=path.name, row=row_number, column="Time"
        )
        times.append(time_s)
        for index, label in enumerate(labels[1:], start=1):
            columns[index - 1].append(
                _numeric(
                    row[index],
                    artifact=path.name,
                    row=row_number,
                    column=label,
                )
            )

    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise ValueError(
            f"FDS DEVC time values must be strictly increasing: {path.name}"
        )

    digest = sha256_file(path)
    return {
        label: DeviceTimeSeries(
            device_id=label,
            unit=units[index],
            times_s=tuple(times),
            values=tuple(columns[index - 1]),
            source_artifact=path.name,
            source_sha256=digest,
        )
        for index, label in enumerate(labels[1:], start=1)
    }


def load_fds_device_series(directory: Path, chid: str) -> dict[str, DeviceTimeSeries]:
    """Load CHID_devc.csv or split CHID_<n>_devc.csv files fail-closed."""

    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"FDS evidence directory does not exist: {directory}")
    pattern = re.compile(rf"{re.escape(chid)}(?:_\d+)?_devc\.csv")
    files = sorted(
        path for path in directory.iterdir() if path.is_file() and pattern.fullmatch(path.name)
    )
    if not files:
        raise ValueError(f"No FDS DEVC CSV artifacts found for CHID {chid!r}")

    combined: dict[str, DeviceTimeSeries] = {}
    for path in files:
        for device_id, series in _read_devc_file(path).items():
            if device_id in combined:
                raise ValueError(
                    f"Duplicate FDS DEVC device ID across output files: {device_id}"
                )
            combined[device_id] = series
    return combined
