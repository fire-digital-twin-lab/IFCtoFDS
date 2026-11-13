"""Kiểm trạng thái OBST theo sự kiện FDS với bộ hẹn giờ một lần."""

from collections import defaultdict
from dataclasses import dataclass
import math
import re

from .acceptance import GateResult, GateStatus
from .smv import grid_bounds, table_start


_EVENT_HEADER = re.compile(r"(SHOW|HIDE)_OBST\s+(\d+)")
_EVENT_TIME_ROUNDING_S = 5.1e-7  # SMV uses F14.6 for the timestamp.


@dataclass(frozen=True)
class DoorTimer:
    timer_id: str
    control_id: str | None
    setpoint_s: float
    initial_present: bool


def _single(record, key, default=None):
    values = record.values.get(key, [default])
    if len(values) != 1:
        raise ValueError(f"Expected a single {record.kind}.{key}: {record.id}")
    return values[0]


def _positive_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def door_timers(parsed, mesh, obstructions):
    times = [record for record in parsed.records if record.kind == "TIME"]
    if len(times) != 1:
        raise ValueError("Door evidence requires one TIME namelist")
    time = times[0]
    end = _single(time, "T_END")
    dt = _single(time, "DT")
    if (
        set(time.values) - {"T_END", "T_BEGIN", "DT", "LOCK_TIME_STEP"}
        or _single(time, "LOCK_TIME_STEP") is not True
        or _single(time, "T_BEGIN", 0) != 0
        or not _positive_number(end) or not _positive_number(dt)
        or dt <= 2 * _EVENT_TIME_ROUNDING_S
    ):
        raise ValueError("Door timing proof requires a locked positive DT, T_BEGIN=0 and finite T_END")

    devices = {r.id: r for r in parsed.records if r.kind == "DEVC"}
    controls = {r.id: r for r in parsed.records if r.kind == "CTRL"}
    surfaces = {r.id for r in parsed.records if r.kind == "SURF"}
    domain = mesh.values["XB"]
    timers = {}
    for obst in obstructions:
        control_id = _single(obst, "CTRL_ID")
        timer_id = _single(obst, "DEVC_ID")
        if (
            not obst.id or _single(obst, "ID") != obst.id
            or _single(obst, "SURF_ID", "INERT") != "INERT" or "INERT" in surfaces
            or set(obst.values) - {"ID", "XB", "SURF_ID", "DEVC_ID", "CTRL_ID"}
            or ("CTRL_ID" in obst.values and not isinstance(control_id, str))
            or ("DEVC_ID" in obst.values and not isinstance(timer_id, str))
            or ("CTRL_ID" in obst.values and "DEVC_ID" in obst.values)
            or any(not domain[i] <= obst.values["XB"][i] < obst.values["XB"][i + 1] <= domain[i + 1] for i in (0, 2, 4))
        ):
            raise ValueError("Door proof requires identified inert OBST contained in the mesh")
        if control_id is None and timer_id is None:
            continue

        initial = None
        if control_id is not None:
            control = controls.get(control_id)
            if (
                control is None or _single(control, "ID") != control_id
                or set(control.values) - {"ID", "FUNCTION_TYPE", "INPUT_ID", "INITIAL_STATE", "LATCH"}
                or _single(control, "FUNCTION_TYPE") != "ANY"
                or _single(control, "LATCH", True) is not True
                or type(_single(control, "INITIAL_STATE")) is not bool
            ):
                raise ValueError(f"Unsupported OBST control: {obst.id}")
            initial = _single(control, "INITIAL_STATE")
            timer_id = _single(control, "INPUT_ID")
            if not isinstance(timer_id, str) or timer_id in controls:
                raise ValueError(f"Ambiguous or nested door control: {obst.id}")

        device = devices.get(timer_id) if isinstance(timer_id, str) and timer_id else None
        if (
            device is None or _single(device, "ID") != timer_id
            or set(device.values) - {"ID", "XYZ", "QUANTITY", "SETPOINT", "INITIAL_STATE", "TIME_AVERAGED"}
            or _single(device, "QUANTITY") != "TIME"
            or _single(device, "TIME_AVERAGED", False) is not False
            or type(_single(device, "INITIAL_STATE", False)) is not bool
        ):
            raise ValueError(f"Unsupported door timer: {obst.id}")
        xyz = device.values.get("XYZ", [])
        setpoint = _single(device, "SETPOINT")
        if (
            len(xyz) != 3 or any(type(x) not in (int, float) for x in xyz)
            or any(not domain[2 * i] < x < domain[2 * i + 1] for i, x in enumerate(xyz))
            or not _positive_number(setpoint) or setpoint + 2 * dt > end
        ):
            raise ValueError(f"Door timer is outside the observable solver time or domain: {obst.id}")
        if initial is None:
            initial = _single(device, "INITIAL_STATE", False)
        elif _single(device, "INITIAL_STATE", False) is not False:
            raise ValueError(f"ANY door control requires an initially false timer input: {obst.id}")
        timers[obst.id] = DoorTimer(timer_id, control_id, setpoint, initial)
    if not timers:
        raise ValueError("Missing supported door controls")
    return dt, end, timers


def _read_events(lines, rows, end):
    start = table_start(lines, "OBST") + 1
    for offset, (label, _) in enumerate(rows):
        fields = lines[start + offset].partition("!")[0].split()
        if len(fields) < 7 or int(fields[6]) != offset + 1:
            raise ValueError(f"Cannot bind SMV event ordinal to OBST: {label}")

    events = defaultdict(list)
    for i in range(start + 2 * len(rows), len(lines)):
        header = lines[i].strip()
        if not header.startswith(("SHOW_OBST", "HIDE_OBST")):
            continue
        match = _EVENT_HEADER.fullmatch(header)
        if match is None or int(match[2]) != 1:
            raise ValueError("Invalid SMV obstruction event mesh")
        raw_index, raw_time = lines[i + 1].split()
        index, time = int(raw_index), float(raw_time)
        if not 1 <= index <= len(rows) or not 0 <= time <= end + _EVENT_TIME_ROUNDING_S:
            raise ValueError("Invalid SMV obstruction event index or time")
        events[rows[index - 1][0]].append((match[1], time))
    return events


def verify_door_timeline(lines, grid_data, timing, evidence):
    dt, end, timers = timing
    grids, rows = grid_data
    try:
        observed = _read_events(lines, rows, end)
    except (ValueError, IndexError) as exc:
        return GateResult(status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence)

    unscheduled = sorted(observed.keys() - timers.keys())
    if unscheduled:
        evidence["unscheduled_obstruction_events"] = {label: observed[label] for label in unscheduled}
        return GateResult(status=GateStatus.FAIL, reason="Solver changed an unscheduled OBST", evidence=evidence)
    by_label = {label: indices for label, indices in rows}
    timeline = evidence["obstruction_timeline"] = {}
    evidence["solver_time_step_s"] = dt
    missing = []
    for label, timer in timers.items():
        events = observed.get(label, [])
        timeline[label] = dict(
            timer_id=timer.timer_id, control_id=timer.control_id,
            setpoint_s=timer.setpoint_s, expected_initial_present=timer.initial_present,
            bounds_m=grid_bounds(by_label[label], grids), events=events,
        )
        initial = [] if timer.initial_present else [("HIDE", 0.0)]
        at_start = [(action, t) for action, t in events if t <= _EVENT_TIME_ROUNDING_S]
        transitions = [(action, t) for action, t in events if t > _EVENT_TIME_ROUNDING_S]
        expected = "HIDE" if timer.initial_present else "SHOW"
        if (
            (at_start and at_start != initial) or len(transitions) > 1
            or any(current[1] < previous[1] for previous, current in zip(events, events[1:]))
        ):
            return GateResult(status=GateStatus.FAIL, reason=f"Unexpected obstruction events: {label}", evidence=evidence)
        if transitions:
            action, event_time = transitions[0]
            # FDS advances the clock, applies the prior control state, then
            # evaluates devices. Sampling plus application can span two steps.
            if action != expected or not (
                timer.setpoint_s - _EVENT_TIME_ROUNDING_S <= event_time
                <= timer.setpoint_s + 2 * dt + _EVENT_TIME_ROUNDING_S
            ):
                return GateResult(status=GateStatus.FAIL, reason=f"Obstruction transition differs from timer: {label}", evidence=evidence)
        if at_start != initial or not transitions:
            missing.append(label)
            continue
        timeline[label].update(
            initial_present=timer.initial_present, final_present=(expected == "SHOW"),
            transition_s=transitions[0][1],
        )
    if missing:
        return GateResult(status=GateStatus.INCONCLUSIVE, reason=f"Missing solver door events: {', '.join(missing)}", evidence=evidence)
    return GateResult(status=GateStatus.PASS, reason="Solver OBST presence and scheduled transition verified", evidence=evidence)
