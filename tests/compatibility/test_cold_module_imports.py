"""Native ingestion must be importable first in a fresh worker process."""

from pathlib import Path
import subprocess
import sys


def test_inventory_can_be_the_first_module_import():
    result = subprocess.run(
        [sys.executable, '-c', 'from ifc_to_fds.modules.bim.api import extract_inventory; assert callable(extract_inventory)'],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
