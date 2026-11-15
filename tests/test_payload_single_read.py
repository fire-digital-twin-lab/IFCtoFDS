"""A payload is read once but still fully verified: same-size corruption, deletion and a directory are refused."""

import pytest

from ifc_to_fds.geometry.package import verify_package
from ifc_to_fds.geometry.storage import payload_dir, read_package, write_package


def corrupt(box_model, tmp_path, change):
    path = tmp_path / "geometry.json"
    write_package(box_model, path)
    payload = next(payload_dir(path).glob("*.bin"))
    change(payload)
    return read_package(path)


def test_flipping_one_byte_without_changing_the_size_is_detected(box_model, tmp_path):
    def flip(payload):
        data = bytearray(payload.read_bytes())
        data[0] ^= 1
        payload.write_bytes(bytes(data))

    with pytest.raises(ValueError, match="corrupted"):
        verify_package(corrupt(box_model, tmp_path, flip))


def test_a_missing_payload_is_refused(box_model, tmp_path):
    with pytest.raises(ValueError, match="corrupted"):
        verify_package(corrupt(box_model, tmp_path, lambda payload: payload.unlink()))


def test_a_directory_in_place_of_a_payload_is_refused(box_model, tmp_path):
    def replace(payload):
        payload.unlink()
        payload.mkdir()

    with pytest.raises(ValueError, match="corrupted"):
        verify_package(corrupt(box_model, tmp_path, replace))


def test_roundtrip_returns_the_same_mesh(box_model, tmp_path):
    package = write_package(box_model, tmp_path / "geometry.json")
    mesh = package["elements"]["fixture:1"]["mesh"]
    assert mesh["vertices"] == box_model.elements[0].mesh.vertices
    assert mesh["faces"] == box_model.elements[0].mesh.faces
