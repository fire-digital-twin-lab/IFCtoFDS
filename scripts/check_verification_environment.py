"""Record reproducible runtime/lock checks and environment blockers, without installing packages."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def check_requirements(text, versions, marker_environment=None):
    selected = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate(marker_environment):
            continue
        installed = versions.get(requirement.name)
        selected.append({"name": requirement.name, "locked": str(requirement.specifier),
                         "installed": installed, "status": "PASS" if installed is not None
                         and requirement.specifier.contains(installed, prereleases=True) else "FAIL"})
    return selected


def inspect_environment(output, solver=None, pyrosim=None, browser=False):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
               "markers": default_environment(), "uv_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()}
    report = {"runtime": runtime, "checks": {}, "simulation": "NOT_VERIFIED"}
    uv = shutil.which("uv")
    if uv:
        command = [uv, "--cache-dir", str(output.parent / "uv-cache"), "export", "--locked", "--offline",
                   "--no-dev", "--extra", "test", "--no-hashes", "--no-emit-project"]
        if browser:
            command += ["--extra", "browser"]
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30,
                                    env={**os.environ, "UV_PYTHON": sys.executable, "UV_PYTHON_DOWNLOADS": "never"})
            versions = {d.metadata["Name"].lower().replace("_", "-"): d.version for d in importlib.metadata.distributions()}
            checks = check_requirements(result.stdout, versions) if result.returncode == 0 else []
            report["checks"]["locked_dependencies"] = {
                "status": "PASS" if checks and all(c["status"] == "PASS" for c in checks) else "FAIL",
                "command": command, "dependencies": checks, "stderr": result.stderr,
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            report["checks"]["locked_dependencies"] = {"status": "BLOCKED", "reason": str(exc)}
    else:
        report["checks"]["locked_dependencies"] = {"status": "BLOCKED", "reason": "uv not available"}
    try:
        probe = subprocess.run([sys.executable, "-c", "import socket; a,b=socket.socketpair(); a.close(); b.close()"],
                               capture_output=True, text=True, timeout=3, cwd=ROOT)
        report["checks"]["loopback_socketpair"] = {
            "status": "PASS" if probe.returncode == 0 else "BLOCKED", "stderr": probe.stderr,
            "scope": "EVENT_LOOP_PREREQUISITE_ONLY",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        report["checks"]["loopback_socketpair"] = {"status": "BLOCKED", "reason": str(exc)}
    for name, configured, default in (("solver", solver, "fds"), ("pyrosim", pyrosim, "pyrosim")):
        executable = str(configured) if configured else shutil.which(default)
        available = bool(executable and Path(executable).is_file())
        report["checks"][name] = {"availability": "AVAILABLE" if available else "UNAVAILABLE",
            "execution": "NOT_RUN", "executable": executable,
            "sha256": hashlib.sha256(Path(executable).read_bytes()).hexdigest() if available else None}
    (output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--solver", type=Path)
    parser.add_argument("--pyrosim", type=Path)
    parser.add_argument("--browser", action="store_true", help="Also check locked browser dependencies")
    args = parser.parse_args(argv)
    report = inspect_environment(args.output, args.solver, args.pyrosim, args.browser)
    checks = [c["status"] for c in report["checks"].values() if "status" in c]
    print(json.dumps({"checks": {n: c.get("status", c.get("availability")) for n, c in report["checks"].items()}}))
    return 1 if "FAIL" in checks else 2 if "BLOCKED" in checks else 0


if __name__ == "__main__":
    raise SystemExit(main())
