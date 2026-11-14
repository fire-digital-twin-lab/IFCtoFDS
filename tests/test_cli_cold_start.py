"""CLI must work from a fresh interpreter.

The in-process suite imports many modules during collection, which hides
circular imports. Each test here starts a new Python process.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TINY = ROOT / "tests" / "baseline" / "fixtures" / "tiny.ifc"


def _run(*args, timeout=300):
    env = dict(os.environ, IFCFDS_SOLVER_AUTODISCOVERY="0", PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "ifc_to_fds", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.parametrize("module", ["ifc_to_fds.fire", "ifc_to_fds.validation.engine",
                                    "ifc_to_fds.validation.checkers.mesh_resolution"])
def test_package_imports_first_in_a_fresh_process(module):
    result = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=ROOT,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]


def test_convert_writes_fds_from_a_fresh_process(tmp_path):
    out = tmp_path / "tiny.fds"
    result = _run("convert", str(TINY), "-o", str(out))
    assert "ImportError" not in result.stderr, result.stderr[-2000:]
    assert out.is_file(), result.stdout[-1000:] + result.stderr[-2000:]
    assert result.returncode in (0, 1, 2), result.stderr[-2000:]


def test_bbox_coordinate_frame_reaches_scope(monkeypatch, tmp_path):
    """model_preparer reads scope.coordinate_frame; the CLI used to nest it in bounding_box."""
    from ifc_to_fds import cli

    seen = {}

    def fake_convert(paths, config, output_directory=None):
        seen.update(config)
        return {"status": "MAPPING_VERIFIED"}

    monkeypatch.setattr(cli, "convert", fake_convert)
    monkeypatch.setattr(cli, "save_artifacts", lambda result, target: None)
    code = cli.main(["convert", str(TINY), "-o", str(tmp_path / "o.fds"),
                     "--bbox", "0", "1", "0", "1", "0", "1", "--coordinate-frame", "WORLD"])
    assert code == 0
    assert seen["scope"]["coordinate_frame"] == "WORLD"
    assert "coordinate_frame" not in seen["scope"]["bounding_box"]
