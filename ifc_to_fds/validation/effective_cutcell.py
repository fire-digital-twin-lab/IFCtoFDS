"""Đối chiếu probe giải tích với thể tích khí và mặt mở GEOM của FDS."""

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ifc_to_fds.geometry.mesh import as_trimesh, self_intersection_evidence, valid_solid
from .acceptance import GateResult, GateStatus
from .parser import parse_fds
from .solver import solver_gates
from .solver_discovery import PINNED_VERSION
from .solver_outputs import load_fds_device_series


CUTCELL_ADAPTER_VERSION = "fds-6.11.1-cutcell-probes-v1"
_NORMAL_VELOCITY = ("U-VELOCITY", "V-VELOCITY", "W-VELOCITY")


class CutCellProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
    bounds_m: tuple[float, float, float, float, float, float]
    expected: float = Field(ge=0)
    tolerance: float = Field(gt=0)
    units: Literal["m2", "m3"]


def _probe_record(probe, domain, cells):
    spans = [probe.bounds_m[i + 1] - probe.bounds_m[i] for i in (0, 2, 4)]
    flat = [axis for axis, span in enumerate(spans) if span == 0]
    if len(flat) != (1 if probe.units == "m2" else 0) or any(span < 0 for span in spans):
        raise ValueError(f"Probe dimensions differ from {probe.units}: {probe.id}")
    if probe.expected > math.prod(span for span in spans if span > 0) + probe.tolerance:
        raise ValueError(f"Probe expectation exceeds its geometric measure: {probe.id}")
    for i, coordinate in enumerate(probe.bounds_m):
        axis = i // 2
        lo, hi = domain[2 * axis:2 * axis + 2]
        index = (coordinate - lo) * cells[axis] / (hi - lo)
        if not 0 <= round(index) <= cells[axis] or abs(index - round(index)) > 1e-7:
            raise ValueError(f"Probe bounds must align with mesh nodes: {probe.id}")
    if flat:
        normal = flat[0]
        if not domain[2 * normal] < probe.bounds_m[2 * normal] < domain[2 * normal + 1]:
            raise ValueError(f"GEOM area probes require an interior grid face: {probe.id}")
        quantity, statistic = _NORMAL_VELOCITY[normal], "AREA"
    else:
        quantity, statistic = "DENSITY", "VOLUME"
    bounds = ",".join(format(x, ".17g") for x in probe.bounds_m)
    return f"&DEVC ID='{probe.id}', XB={bounds}, QUANTITY='{quantity}', SPATIAL_STATISTIC='{statistic}', TIME_AVERAGED=.FALSE. /"


def _instrument(fds_text, probes):
    parsed = parse_fds(fds_text)
    if parsed.errors or parsed.unsupported:
        raise ValueError("Cut-cell probe deck has unsupported FDS syntax")
    records = {}
    for record in parsed.records:
        if record.kind not in {"HEAD", "TAIL", "TIME", "MESH", "GEOM"} or record.kind in records:
            raise ValueError("Cut-cell probes require a static diagnostic deck with one mesh and one GEOM")
        records[record.kind] = record
    if set(records) != {"HEAD", "TAIL", "TIME", "MESH", "GEOM"}:
        raise ValueError("Cut-cell probe deck is incomplete")

    time = records["TIME"].values
    end = time.get("T_END", [])
    if set(time) - {"T_END", "DT"} or len(end) != 1 or type(end[0]) is not float or end[0] <= 0:
        raise ValueError("Cut-cell probes need a positive diagnostic run beginning at t=0")
    domain, cells = (records["MESH"].values[key] for key in ("XB", "IJK"))
    geom = records["GEOM"]
    if set(geom.values) - {"ID", "VERTS", "FACES", "SURF_ID"} or geom.values.get("SURF_ID", ["INERT"]) != ["INERT"]:
        raise ValueError("Cut-cell probes require one inert GEOM")
    mesh = geom.mesh()
    if not valid_solid(mesh) or self_intersection_evidence(mesh)["status"] != "CLEAN":
        raise ValueError("Cut-cell probes require a closed, outward oriented GEOM")
    if len(as_trimesh(mesh).split(only_watertight=False, repair=False)) != 1:
        raise ValueError("Cut-cell probes require a single GEOM shell")
    vertices = np.asarray(mesh.vertices, dtype=float)
    if np.any(vertices <= domain[::2]) or np.any(vertices >= domain[1::2]):
        raise ValueError("Cut-cell probes require GEOM strictly inside the mesh")
    if not probes or len({probe.id for probe in probes}) != len(probes):
        raise ValueError("Cut-cell probes require unique probe IDs")
    if {probe.units for probe in probes} != {"m2", "m3"} or all(
        probe.bounds_m == tuple(domain) for probe in probes if probe.units == "m3"
    ):
        raise ValueError("Cut-cell probes require local volume and open-face area checks")
    additions = "\n".join(_probe_record(probe, domain, cells) for probe in probes)
    tail, _ = records["TAIL"].text_span
    return fds_text[:tail] + additions + "\n" + fds_text[tail:], records["HEAD"].values["CHID"][0]


def certify_cutcell_geometry(fds_text, requested_probes, config):
    """Chạy một deck có probe độc lập, giữ kết quả theo từng vị trí đo."""
    evidence = {
        "adapter_version": CUTCELL_ADAPTER_VERSION,
        "scope": "DECLARED_PROBES_AT_INITIALIZATION",
        "base_fds_sha256": hashlib.sha256(fds_text.encode("utf-8")).hexdigest(),
    }
    if config.solver_version != PINNED_VERSION:
        return GateResult(status=GateStatus.INCONCLUSIVE, reason="Cut-cell probes require FDS 6.11.1", evidence=evidence)
    try:
        probes = [CutCellProbe.model_validate(value) for value in requested_probes]
        instrumented, chid = _instrument(fds_text, probes)
    except (ValueError, TypeError, RuntimeError, IndexError) as exc:
        return GateResult(status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence)
    digest = hashlib.sha256(instrumented.encode("utf-8")).hexdigest()
    evidence.update(instrumented_fds_sha256=digest, probes=[probe.model_dump(mode="json") for probe in probes])

    solver, _ = solver_gates(instrumented, config)
    evidence["solver_status"] = solver.status.value
    if solver.status != GateStatus.PASS:
        return GateResult(status=solver.status, reason=solver.reason, evidence=evidence)
    try:
        run = solver.evidence
        if (
            run.get("fds_sha256") != digest or PINNED_VERSION not in run.get("reported_versions", [])
            or not re.fullmatch(r"[a-f0-9]{64}", run.get("sha256", ""))
        ):
            raise ValueError("Cut-cell probe run identity differs from the instrumented deck")
        directory = Path(run["directory"])
        evidence.update(solver_sha256=run["sha256"], directory=str(directory))
        series = load_fds_device_series(directory, chid)
        if set(series) != {probe.id for probe in probes}:
            raise ValueError("Solver DEVC output differs from the declared cut-cell probes")
        measurements = {}
        mismatches = []
        for probe in probes:
            observed = series[probe.id]
            if (
                observed.unit != probe.units or observed.times_s[0] != 0
                or run.get("files", {}).get(observed.source_artifact) != observed.source_sha256
            ):
                raise ValueError(f"Missing sealed t=0 sample with expected units: {probe.id}")
            measured = observed.values[0]
            error = abs(measured - probe.expected)
            measurements[probe.id] = {
                "expected": probe.expected, "measured": measured, "abs_error": error,
                "tolerance": probe.tolerance, "units": observed.unit, "time_s": 0.0,
                "source_artifact": observed.source_artifact, "source_sha256": observed.source_sha256,
            }
            if measured < 0 or error > probe.tolerance:
                mismatches.append(probe.id)
        evidence["measurements"] = measurements
        result = GateResult(
            status=GateStatus.FAIL if mismatches else GateStatus.PASS,
            reason=("Cut-cell probes differ: " + ", ".join(mismatches)) if mismatches else "Declared cut-cell volume and open area probes matched at t=0",
            evidence=evidence,
        )
        (directory / "cutcell-probes.json").write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8",
        )
        return result
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return GateResult(status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence)
