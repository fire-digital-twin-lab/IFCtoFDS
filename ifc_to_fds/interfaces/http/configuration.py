"""Decode and validate HTTP configuration, preserving operator-only settings."""
import json
import os
from pathlib import Path
from fastapi import HTTPException
from ifc_to_fds.domain.scope import SpatialScope
from ifc_to_fds.domain.validation import AuditConfig

def configuration_value(
    text, cell_size=None, storey=None, all_geom=None, include_review=None, profile=None
):
    try:
        config = json.loads(text or "{}")
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a JSON object")
        for key, value in (
            ("cell_size", cell_size),
            ("all_geom", all_geom),
            ("include_review", include_review),
            ("profile", profile),
        ):
            if value is not None:
                config[key] = value
        if storey:
            config.setdefault("scope", {})["storeys"] = [storey]
        import math

        cell = float(config.get("cell_size", 0.2))
        if not math.isfinite(cell) or cell <= 0:
            raise ValueError("cell_size must be finite and positive")
        config["cell_size"] = cell
        SpatialScope.model_validate(config.get("scope", {}))
        AuditConfig.model_validate(config.get("audit", {}))
        case = config.get("reference_case")
        if case:
            registered = json.loads(os.getenv("IFCFDS_REFERENCE_CASES", "{}"))
            if case not in registered:
                raise ValueError(
                    "Choose a registered reference case ID; server paths are not accepted"
                )
            entry = registered[case]
            config["reference_case"] = str(
                Path(entry if isinstance(entry, str) else entry["path"]).resolve()
            )
        # Executables are local operator configuration, never selectable by an upload.
        if any(
            config.get("audit", {}).get(k)
            for k in (
                "solver_executable",
                "solver_evidence_directory",
                "boundary_fixture_certificate",
            )
        ):
            raise ValueError(
                "Solver executable must be configured by the local operator"
            )
        if os.getenv("IFCFDS_SOLVER"):
            config.setdefault("audit", {})["solver_executable"] = os.environ[
                "IFCFDS_SOLVER"
            ]
        if os.getenv("IFCFDS_BOUNDARY_CERTIFICATE"):
            config.setdefault("audit", {})["boundary_fixture_certificate"] = os.environ[
                "IFCFDS_BOUNDARY_CERTIFICATE"
            ]
        from ifc_to_fds.application.dto.configuration import validate_configuration

        return validate_configuration(config)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc))

