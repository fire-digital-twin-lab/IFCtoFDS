"""Kiểm tra cú pháp và fail-closed của công cụ bảo trì Docker named volume."""

from pathlib import Path
import os
import shutil
import subprocess

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "production-volume-maintenance.sh"
)


@pytest.mark.skipif(
    os.name != "posix" or shutil.which("bash") is None,
    reason="Script bảo trì Docker/Linux: không kiểm thử qua alias WSL của Windows",
)
def test_offline_volume_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
    os.name != "posix" or shutil.which("bash") is None,
    reason="Script bảo trì Docker/Linux: không kiểm thử qua alias WSL của Windows",
)
@pytest.mark.parametrize("name", ["../escape", "foo/bar", ".hidden", "bad name"])
def test_offline_volume_script_rejects_unsafe_backup_names_before_docker(name):
    result = subprocess.run(
        ["bash", str(SCRIPT), "backup", "ifctofds:ci", "/tmp", name],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Unsafe backup name" in result.stderr


@pytest.mark.skipif(
    os.name != "posix" or shutil.which("bash") is None,
    reason="Script bảo trì Docker/Linux: không kiểm thử qua alias WSL của Windows",
)
def test_offline_volume_script_requires_explicit_operation():
    result = subprocess.run(
        ["bash", str(SCRIPT), "restore", "ifctofds:ci", "/tmp"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Usage:" in result.stderr
