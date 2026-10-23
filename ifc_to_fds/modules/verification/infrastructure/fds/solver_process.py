"""Pinned solver runs with durable evidence and killable process trees."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import platform
import psutil
from ifc_to_fds.runtime.diagnostics import operation
from ifc_to_fds.domain.validation import GateResult, GateStatus
from ifc_to_fds.modules.verification.application.effective_obstructions import effective_obstructions
from ifc_to_fds.modules.verification.application.solver_completion import (
    FATAL_DIAGNOSTIC,
    assess_completion,
)
from ifc_to_fds.modules.verification.application.solver_surface import verify_solver_surfaces
from ifc_to_fds.modules.verification.infrastructure.fds.bingeom import read_bingeom


def stop_tree(process):
    try:
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
    except psutil.NoSuchProcess:
        pass


@operation("SOLVER")
def solver_gates(fds_text, config):
    executable = config.solver_executable or shutil.which("fds")
    effective = GateResult(
        status=GateStatus.INCONCLUSIVE,
        reason="Effective geometry has not been proved from solver output",
    )
    if not executable:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="FDS executable not installed/configured",
        ), effective
    path = Path(executable).resolve()
    evidence = dict(
        required_version=config.solver_version,
        adapter_version="static-openings-and-geom-surfaces-0.5.2",
        platform=platform.platform(),
        configuration_sha256=hashlib.sha256(
            config.model_dump_json().encode()
        ).hexdigest(),
        fds_sha256=hashlib.sha256(fds_text.encode()).hexdigest(),
    )
    directory = None
    try:
        evidence.update(
            executable=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        )
        directory = (
            Path(config.solver_evidence_directory or ".cache/solver-evidence").resolve()
            / uuid.uuid4().hex
        )
        directory.mkdir(parents=True)
        evidence["directory"] = str(directory)
        input_path = directory / "audit.fds"
        input_path.write_bytes(fds_text.encode())
        command = [str(path), input_path.name]
        evidence.update(
            command=command,
            timeout_s=config.solver_timeout_s,
            environment={
                "OMP_NUM_THREADS": "1",
                "mpi_runtime_directory": str(path.parent / "mpi"),
            },
        )
        runtime = {
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "PATH": str(path.parent / "mpi") + os.pathsep + os.environ.get("PATH", ""),
        }
        probe = subprocess.Popen(
            [str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=runtime,
            cwd=directory,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            version_output, _ = probe.communicate(
                timeout=min(15, config.solver_timeout_s)
            )
        except subprocess.TimeoutExpired:
            stop_tree(probe)
            version_output, _ = probe.communicate()
            (directory / "version.log").write_bytes(version_output)
            raise subprocess.TimeoutExpired(
                [str(path)], min(15, config.solver_timeout_s)
            )
        (directory / "version.log").write_bytes(version_output)
        process = subprocess.Popen(
            command,
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            env={
                **os.environ,
                "OMP_NUM_THREADS": "1",
                "PATH": str(path.parent / "mpi")
                + os.pathsep
                + os.environ.get("PATH", ""),
            },
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        timeout = False
        try:
            stdout, stderr = process.communicate(timeout=config.solver_timeout_s)
        except subprocess.TimeoutExpired:
            timeout = True
            stop_tree(process)
            stdout, stderr = process.communicate()
        (directory / "stdout.log").write_bytes(stdout)
        (directory / "stderr.log").write_bytes(stderr)
        evidence.update(returncode=process.returncode, timed_out=timeout)
        combined = stdout.decode(errors="replace") + stderr.decode(errors="replace")
        combined += "\n".join(
            f.read_text(encoding="utf-8", errors="replace")
            for f in directory.glob("*.out")
        )
        versions = re.findall(
            r"(?:FDS[-\s]+|FDS\s+Version\s*[:=]?\s*)(\d+\.\d+\.\d+)",
            version_output.decode(errors="replace") + combined,
            re.I,
        )
        evidence["reported_versions"] = versions
        evidence["files"] = {
            f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in directory.iterdir()
            if f.is_file()
        }
        (directory / "run.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
        if timeout:
            status, reason = GateStatus.INCONCLUSIVE, "FDS initialization timed out"
        elif config.solver_version not in versions:
            status, reason = (
                GateStatus.INCONCLUSIVE,
                "Pinned solver version not confirmed",
            )
        elif process.returncode or FATAL_DIAGNOSTIC.search(combined):
            status, reason = (
                GateStatus.FAIL,
                "FDS rejected input or exited with an error",
            )
        else:
            status, reason, completion = assess_completion(fds_text, combined)
            evidence["completion"] = completion
        evidence["fatal_diagnostics"] = [m.group(0).strip() for m in FATAL_DIAGNOSTIC.finditer(combined)]
        evidence["status"] = status.value
        evidence["reason"] = reason
        (directory / "run.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        if status == GateStatus.PASS:
            surface = verify_solver_surfaces(
                fds_text,
                {f.name: f.read_bytes() for f in directory.glob("*.bingeom")},
                config,
                read_bingeom,
            )
            evidence["solver_surface_geometry"] = surface.model_dump(mode="json")
            (directory / "surface_geometry.json").write_text(surface.model_dump_json(indent=2), encoding="utf-8")
            if surface.status == GateStatus.FAIL:
                status, reason = GateStatus.FAIL, "Solver-emitted GEOM surface validation failed"
            smv = list(directory.glob("*.smv"))
            if len(smv) == 1:
                effective = effective_obstructions(
                    fds_text, smv[0].read_text(encoding="utf-8", errors="replace")
                )
                effective.evidence.update(
                    fds_sha256=evidence["fds_sha256"],
                    solver_sha256=evidence["sha256"],
                    directory=str(directory),
                )
        (directory / "effective.json").write_text(
            effective.model_dump_json(indent=2), encoding="utf-8"
        )
        evidence.update(status=status.value, reason=reason)
        (directory / "run.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return GateResult(status=status, reason=reason, evidence=evidence), effective
    except (OSError, subprocess.TimeoutExpired) as exc:
        evidence.update(
            termination_reason=str(exc),
            timed_out=isinstance(exc, subprocess.TimeoutExpired),
        )
        if directory is not None:
            (directory / "run.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
        return GateResult(
            status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence
        ), effective
