"""FDS 6.11.1 little-endian CAD BINGEOM, with checked Fortran record markers.

Format: pinned Source/geom.f90 READ_GEOM writer, also FDS User Guide 27.19.
Only static surface solids (GEOM_TYPE=1, N_VOLUS=0) are supported here.
"""

import struct

import numpy as np

from ifc_to_fds.domain.bim import TriangleMesh


def read_bingeom(data):
    offset = 0

    def record():
        nonlocal offset
        if offset + 8 > len(data):
            raise ValueError("Truncated BINGEOM record")
        size = struct.unpack_from("<i", data, offset)[0]
        if size < 0 or offset + 8 + size > len(data):
            raise ValueError("Invalid BINGEOM record length")
        end = offset + 4 + size
        if struct.unpack_from("<i", data, end)[0] != size:
            raise ValueError("BINGEOM record markers differ")
        payload = memoryview(data)[offset + 4 : end]
        offset = end + 4
        return payload

    kind = record()
    if len(kind) != 4 or struct.unpack("<i", kind)[0] != 1:
        raise ValueError("Unsupported BINGEOM geometry type/endianness")
    counts = record()
    if len(counts) != 16:
        raise ValueError("Invalid BINGEOM header")
    vertices, faces, surfaces, volumes = struct.unpack("<4i", counts)
    if vertices < 4 or faces < 4 or surfaces < 1 or volumes != 0:
        raise ValueError("Unsupported BINGEOM counts/volumes")
    v, f, s, vol = record(), record(), record(), record()
    if (
        len(v) != vertices * 24
        or len(f) != faces * 12
        or len(s) != faces * 4
        or len(vol) != 0
        or offset != len(data)
    ):
        raise ValueError("BINGEOM payload lengths differ from header")
    positions = np.frombuffer(v, dtype="<f8").reshape(-1, 3)
    indices = np.frombuffer(f, dtype="<i4").reshape(-1, 3)
    face_surfaces = np.frombuffer(s, dtype="<i4")
    if (
        not np.isfinite(positions).all()
        or (indices < 1).any()
        or (indices > vertices).any()
        or (face_surfaces < 1).any()
        or (face_surfaces > surfaces).any()
    ):
        raise ValueError("Invalid BINGEOM vertex/face/surface data")
    return (
        TriangleMesh(vertices=positions.tolist(), faces=(indices - 1).tolist()),
        face_surfaces.tolist(),
    )
