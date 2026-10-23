"""A text parser must not initialize native conversion or the serializer."""

from pathlib import Path
import subprocess
import sys


def test_parser_runs_first_without_native_kernel_or_serializer():
    code = '''
import sys
from ifc_to_fds.modules.fds.api import parse_fds
parsed = parse_fds("&HEAD CHID='fixture' / &TIME T_END=0 / &MESH IJK=2,2,2, XB=0,2,0,2,0,2 / &OBST ID='wall', XB=0,1,0,1,0,1 / &TAIL /")
assert not parsed.errors, parsed.errors
assert parsed.primitives[0].id == 'wall'
assert 'ifcopenshell' not in sys.modules
assert 'ifc_to_fds.modules.fds.application.serializer' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[3],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
