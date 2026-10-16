"""Pinned, isolated solver invocation. Successful startup is not effective geometry proof."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from .acceptance import GateResult, GateStatus
from .effective import effective_obstructions


def solver_gates(fds_text, config):
    executable = config.solver_executable or shutil.which("fds")
    effective = GateResult(
        status=GateStatus.INCONCLUSIVE,
        reason="Solver cut-cell/obstruction output comparison is not available; startup alone does not prove effective geometry",
    )
    if not executable:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="FDS executable not installed/configured",
        ), effective
    path = Path(executable).resolve()
    try:
        executable_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return GateResult(
            status=GateStatus.INCONCLUSIVE, reason=f"Solver unavailable: {exc}"
        ), effective
    evidence = dict(
        executable=str(path),
        sha256=executable_hash,
        required_version=config.solver_version,
    )
    try:
        with tempfile.TemporaryDirectory(prefix="ifcfds-solver-") as directory:
            input_path = Path(directory) / "audit.fds"
            input_path.write_text(fds_text, encoding="utf-8")
            result = subprocess.run(
                [str(path), input_path.name],
                cwd=directory,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=config.solver_timeout_s,
                env={**os.environ, "OMP_NUM_THREADS": "1"},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            logs = result.stdout + "\n" + result.stderr
            files = {}
            for f in Path(directory).glob("*"):
                if f.suffix.lower() in (".out", ".err"):
                    files[f.name] = f.read_text(encoding="utf-8", errors="replace")
            combined = logs + "\n" + "\n".join(files.values())
            evidence.update(returncode=result.returncode, log=logs, output_logs=files)
            versions = re.findall(
                r"(?:Version|FDS)\s*[:=]?\s*(\d+\.\d+\.\d+)", combined, re.I
            )
            evidence["reported_versions"] = versions
            if config.solver_version not in versions:
                return GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="Pinned solver version not confirmed",
                    evidence=evidence,
                ), effective
            if result.returncode or re.search(
                r"ERROR:|ERROR\([0-9]+\)|STOP:.*ERROR", combined, re.I
            ):
                return GateResult(
                    status=GateStatus.FAIL,
                    reason="FDS rejected input or exited with an error",
                    evidence=evidence,
                ), effective
            if not re.search(
                r"completed successfully|successfully completed", combined, re.I
            ):
                return GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason="FDS normal completion not confirmed",
                    evidence=evidence,
                ), effective
            smv_files = list(Path(directory).glob("*.smv"))
            if len(smv_files) == 1:
                effective = effective_obstructions(
                    fds_text, smv_files[0].read_text(encoding="utf-8", errors="replace")
                )
            return GateResult(
                status=GateStatus.PASS,
                reason="Pinned FDS initialization completed",
                evidence=evidence,
            ), effective
    except subprocess.TimeoutExpired:
        return GateResult(
            status=GateStatus.INCONCLUSIVE,
            reason="FDS initialization timed out",
            evidence=evidence,
        ), effective
    except OSError as exc:
        return GateResult(
            status=GateStatus.INCONCLUSIVE, reason=str(exc), evidence=evidence
        ), effective
