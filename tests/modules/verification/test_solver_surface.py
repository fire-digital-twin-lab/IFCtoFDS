from pathlib import Path
import hashlib
import json
import struct

import pytest

from ifc_to_fds.domain.validation import AuditConfig
from ifc_to_fds.modules.verification.application.solver_surface import (
    verify_solver_surfaces,
)
from ifc_to_fds.modules.verification.infrastructure.fds.bingeom import read_bingeom

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/solver/fds-6.11.1"


def native():
    return (FIXTURES / "geom.fds").read_text(), (
        FIXTURES / "acceptance_cube.bingeom"
    ).read_bytes()


def gate(text, data):
    return verify_solver_surfaces(text, data, AuditConfig(), read_bingeom)


def test_native_binary_surface_is_proved_separately_from_cut_cells():
    text, data = native()
    result = gate(text, {"acceptance_cube.bingeom": data})
    assert result.status == "PASS", result.reason
    assert result.evidence["cut_cell_occupancy"] == "NOT_VERIFIED"
    assert result.required is False


def test_solver_fixture_provenance_hashes_match():
    metadata = json.loads((FIXTURES / "provenance.json").read_text())
    for name, expected in metadata["files"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize(
    "mutation",
    ["truncated", "record_marker", "negative_length", "coordinates", "surface"],
)
def test_corrupted_native_binary_never_passes(mutation):
    text, raw = native()
    data = bytearray(raw)
    if mutation == "truncated":
        data = data[:-1]
    elif mutation == "record_marker":
        struct.pack_into("<i", data, 8, 123)
    elif mutation == "negative_length":
        struct.pack_into("<i", data, 0, -1)
    elif mutation == "coordinates":
        struct.pack_into("<d", data, 40, 1.25)
    else:
        struct.pack_into("<i", data, 392, 999)
    assert gate(text, {"acceptance_cube.bingeom": bytes(data)}).status == "FAIL"


def test_missing_extra_or_renamed_solver_binary_is_rejected():
    text, data = native()
    for files in (
        {},
        {"unexpected.bingeom": data},
        {"acceptance_cube.bingeom": data, "extra.bingeom": data},
    ):
        assert gate(text, files).status == "FAIL"


@pytest.mark.parametrize("permutation", ["unchanged", "faces_only", "faces_and_surfaces", "vertices"])
def test_multiple_surfaces_are_bound_to_the_corresponding_triangles(permutation):
    from ifc_to_fds.modules.fds.api import parse_fds

    text, raw = native()
    text = text.replace("&GEOM", "&SURF ID='other' /\n&GEOM")
    text = text.replace("SURF_ID='solid'", "SURF_ID='solid','other'")
    # Change the second face to SURF 2, in both serialized and solver data.
    text = text.replace("1,4,3,1", "1,4,3,2")
    assert not parse_fds(text).errors
    data = bytearray(raw)
    struct.pack_into("<i", data, 24, 2)  # N_SURFS in native header
    struct.pack_into("<i", data, 396, 2)  # Second per-face SURF index
    if permutation in ("faces_only", "faces_and_surfaces"):
        data[240:264] = data[252:264] + data[240:252]
        if permutation == "faces_and_surfaces":
            data[392:400] = data[396:400] + data[392:396]
    elif permutation == "vertices":
        # Reindex the first two vertices while preserving all geometric faces.
        data[40:88] = data[64:88] + data[40:64]
        for offset in range(240, 384, 4):
            vertex = struct.unpack_from("<i", data, offset)[0]
            if vertex in (1, 2):
                struct.pack_into("<i", data, offset, 3 - vertex)
    result = gate(text, {"acceptance_cube.bingeom": bytes(data)})
    assert result.status == ("FAIL" if permutation == "faces_only" else "PASS"), result.reason
