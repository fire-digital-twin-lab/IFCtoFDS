"""Prepare a separate cold-flow check without changing accepted mapping bytes."""

import hashlib
import math
import re

from ifc_to_fds.modules.fds.api import parse_fds


def prepare_geometry_run(text, duration_s=1.0):
    """Only TIME changes; no fire, operational MEP, domain or geometry is inferred.

    This deliberately accepts only the static subset understood by our parser.
    The derived file needs its own solver evidence and is not a fire scenario.
    """
    if isinstance(duration_s, bool) or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("Cold-flow duration must be finite and positive")
    parsed = parse_fds(text)
    if parsed.errors or parsed.unsupported:
        raise ValueError(
            f"Unsupported static input: {parsed.errors + parsed.unsupported}"
        )
    times = [r for r in parsed.records if r.kind == "TIME"]
    if len(times) != 1 or times[0].values != {"T_END": [0.0]}:
        raise ValueError("Cold-flow companion requires one setup-only TIME record")
    matches = list(re.finditer(r"^[ \t]*&TIME\b[^/]*\/", text, re.I | re.M))
    if len(matches) != 1:
        raise ValueError("Cannot isolate setup-only TIME record safely")
    match = matches[0]
    derived = (
        text[: match.start()] + f"&TIME T_END={duration_s:.17g} /" + text[match.end() :]
    )
    evidence = {
        "scope": "COLD_FLOW_GEOMETRY_CHECK_ONLY",
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "derived_sha256": hashlib.sha256(derived.encode()).hexdigest(),
        "duration_s": duration_s,
        "changes": [
            {"namelist": "TIME", "field": "T_END", "before": 0.0, "after": duration_s}
        ],
        "geometry_changed": False,
        "fire_scenario": "NOT_CONFIGURED",
        "operational_mep": "NOT_CONFIGURED",
    }
    return derived, evidence
