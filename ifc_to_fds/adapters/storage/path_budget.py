"""Fail before any work when an artifact path would exceed the Windows path limit."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import winreg
except ImportError:
    winreg = None

WINDOWS_MAX_PATH = 260  # characters including the terminating NUL
WORK_PREFIX = ".ifcfds-work-"  # tempfile adds 8 random characters
STAGING_PREFIX = ".staging-"  # followed by 12 hex characters
BACKUP_PREFIX = ".backup-"
UNIQUE_HEX = 12  # enough to keep concurrent runs in one folder apart; 32 hex only cost 20 characters of path
_PAYLOAD = "0" * 64 + ".bin"  # content-addressed geometry payload name


def long_paths_enabled() -> bool:
    """True when this process can use paths of 260 characters or more (always on non-Windows)."""
    if os.name != "nt" or winreg is None:
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
    except OSError:
        return False


def longest_artifact_path(output) -> Path:
    """The deepest path a conversion to `output` creates: a geometry payload in the work, staging, backup or final folder."""
    target = Path(output).resolve()
    stem = target.stem
    candidates = [
        target.parent / (WORK_PREFIX + "x" * 8) / "model_geometry.payloads" / _PAYLOAD,
        target.parent / (STAGING_PREFIX + "0" * UNIQUE_HEX) / f"{stem}_geometry.payloads" / _PAYLOAD,
        target.parent / (BACKUP_PREFIX + "0" * UNIQUE_HEX) / f"{stem}_geometry.payloads" / _PAYLOAD,
        target.parent / f"{stem}_geometry.payloads" / _PAYLOAD,
    ]
    return max(candidates, key=lambda p: len(str(p)))


def check_output_path_budget(output, *, limit: int = WINDOWS_MAX_PATH, long_paths: Optional[bool] = None) -> None:
    """Raise ValueError naming the output folder when its artifacts cannot be written on this system."""
    if long_paths is None:
        long_paths = long_paths_enabled()
    if long_paths:
        return
    longest = longest_artifact_path(output)
    if len(str(longest)) >= limit:
        raise ValueError(
            f"Output folder is too deep: a geometry payload would need a path of {len(str(longest))} characters "
            f"and Windows rejects paths of {limit} or more unless LongPathsEnabled=1. "
            "Choose a shorter output folder (nothing was written)."
        )
