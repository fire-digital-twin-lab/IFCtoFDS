"""Interpret pinned FDS completion and time progress, independently of processes."""

import re

from ifc_to_fds.domain.validation import GateStatus
from ifc_to_fds.modules.fds.api import parse_fds

FATAL_DIAGNOSTIC = re.compile(
    r"^\s*(?:ERROR(?:\(\d+\))?\s*:|STOP:.*\bERROR\b).*$", re.I | re.M
)
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?"


def assess_completion(fds_text, output):
    parsed = parse_fds(fds_text)
    times = [r.values.get("T_END", []) for r in parsed.records if r.kind == "TIME"]
    evidence = {"mode": "UNKNOWN", "scope": "SOLVER_EXECUTION_ONLY"}
    if (
        parsed.errors
        or len(times) != 1
        or len(times[0]) != 1
        or isinstance(times[0][0], bool)
        or not isinstance(times[0][0], (int, float))
        or times[0][0] < 0
    ):
        return (
            GateStatus.INCONCLUSIVE,
            "Unambiguous nonnegative T_END required",
            evidence,
        )
    end = times[0][0]
    evidence.update(mode="SETUP_ONLY" if end == 0 else "TRANSIENT", requested_end_s=end)
    completed = bool(
        re.search(
            r"^\s*STOP:\s*FDS (?:completed successfully|successfully completed)\b",
            output,
            re.I | re.M,
        )
    )
    setup = bool(re.search(r"^\s*STOP:\s*Set-up only\b", output, re.I | re.M))
    if end == 0:
        return (
            GateStatus.PASS if completed or setup else GateStatus.INCONCLUSIVE,
            (
                "Pinned FDS setup completed; no time integration"
                if completed or setup
                else "FDS setup completion not confirmed"
            ),
            evidence,
        )
    # FDS 6.11.1 prints the current simulation time to five decimal places.
    # The allowance below concerns that log rounding, not geometry/physics.
    steps = [int(x) for x in re.findall(r"\bTime Step\s*:?\s*(\d+)", output, re.I)]
    observed = [
        float(x.replace("D", "E").replace("d", "e"))
        for x in re.findall(
            rf"(?:Simulation Time|Total Time):\s*({NUMBER})\s*s\b",
            output,
            re.I,
        )
    ]
    final = max(observed, default=0.0)
    evidence.update(
        observed_end_s=final, time_steps=max(steps, default=0), log_rounding_s=0.000005
    )
    if (
        completed
        and not setup
        and final > 0
        and final + 0.000005 >= end
        and max(steps, default=0) > 0
    ):
        return GateStatus.PASS, "Pinned FDS reached requested end time", evidence
    return (
        GateStatus.INCONCLUSIVE,
        "FDS time integration to requested end not confirmed",
        evidence,
    )
