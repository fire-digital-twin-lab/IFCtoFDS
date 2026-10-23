"""Separate editor handoff from complete effective-geometry verification."""


def summarize_handoff(report):
    required = (
        "syntax",
        "mapping",
        "setup_solver",
        "cold_flow",
        "roundtrip_geometry",
        "roundtrip_solver",
        "pyrosim_import",
    )

    def summarize(names, scope):
        states = {name: report.get(name, {}).get("status", "NOT_RUN") for name in names}
        status = (
            "FAIL"
            if "FAIL" in states.values()
            else (
                "PASS"
                if all(s == "PASS" for s in states.values())
                else "BLOCKED" if "BLOCKED" in states.values() else "INCONCLUSIVE"
            )
        )
        return {
            "status": status,
            "scope": scope,
            "simulation": "NOT_VERIFIED",
            "requirements": states,
            "pending": [name for name, value in states.items() if value != "PASS"],
        }

    return (
        summarize(required, "GEOMETRY_MAPPING_AND_EDITOR_HANDOFF"),
        summarize(
            (*required, "effective_geometry", "roundtrip_effective_geometry"),
            "STATIC_MAPPING_AND_EFFECTIVE_GEOMETRY_VERIFICATION",
        ),
    )
