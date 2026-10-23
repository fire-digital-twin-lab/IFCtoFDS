"""Adversarial source/solver clearances, including domain boundaries."""

import pytest

from ifc_to_fds.modules.verification.application.effective_obstructions import effective_obstructions


def case(boxes, snapped, domain=(0, 1, 0, 1, 0, 1)):
    text = "&HEAD CHID='clearance' /\n&TIME T_END=0 /\n"
    text += "&MESH IJK=10,10,10, XB=" + ",".join(map(str, domain)) + " /\n"
    for pid, xb in boxes.items():
        text += f"&OBST ID='{pid}', XB=" + ",".join(map(str, xb)) + " /\n"
    smv = ""
    for axis, tag in enumerate(("TRNX", "TRNY", "TRNZ")):
        low, high = domain[2 * axis : 2 * axis + 2]
        smv += tag + "\n0\n"
        smv += "".join(f"{i} {low + i / 10 * (high - low):.5f}\n" for i in range(11))
    smv += f"OBST\n{len(boxes)}\n"
    smv += "".join("0 0 0 0 0 0 ! " + pid + "\n" for pid in boxes)
    for pid in boxes:
        indices = []
        for axis in range(3):
            low, high = domain[2 * axis : 2 * axis + 2]
            indices.extend(round((x - low) / (high - low) * 10)
                           for x in snapped[pid][2 * axis : 2 * axis + 2])
        smv += " ".join(map(str, indices)) + "\n"
    return text + "&TAIL /\n", smv


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("side", (0, 1))
def test_subcell_boundary_passage_cannot_pass(axis, side):
    source = [0.4, 0.6, 0.4, 0.6, 0.4, 0.6]
    source[2 * axis:2 * axis + 2] = [0.04, 0.6] if side == 0 else [0.4, 0.96]
    snapped = source[:]
    snapped[2 * axis + side] = float(side)
    gate = effective_obstructions(*case({"wall": source}, {"wall": snapped}))
    assert gate.status == "FAIL", gate.model_dump_json()
    assert "boundary" in gate.reason.lower()


def test_preserved_boundary_clearance_has_topology_evidence():
    box = [0.1, 0.6, 0, 1, 0, 1]
    gate = effective_obstructions(*case({"wall": box}, {"wall": box}))
    assert gate.status == "PASS", gate.reason
    assert gate.evidence["air_connectivity"]["source_components"] == 2
    assert gate.evidence["air_connectivity"]["effective_components"] == 2


@pytest.mark.parametrize("cover_count", (1, 2))
@pytest.mark.parametrize("cover_extent", (0.2, 0.6))
def test_covered_boundary_face_snapping_preserves_the_solid_union(cover_count, cover_extent):
    boxes = {"buried": [0.04, 0.5, 0.4, 0.6, 0.4, 0.6]}
    for i in range(cover_count):
        boxes[f"cover-{i}"] = [0, cover_extent, i / cover_count, (i + 1) / cover_count, 0, 1]
    snapped = {**boxes, "buried": [0, 0.5, 0.4, 0.6, 0.4, 0.6]}
    gate = effective_obstructions(*case(boxes, snapped))
    assert gate.status == "PASS", gate.model_dump_json()


def test_partial_cover_cannot_hide_the_exposed_boundary_passage_closing():
    boxes = {"cover": [0, 0.6, 0, 0.5, 0, 1], "wall": [0.04, 0.5, 0.4, 0.6, 0.4, 0.6]}
    snapped = {**boxes, "wall": [0, 0.5, 0.4, 0.6, 0.4, 0.6]}
    gate = effective_obstructions(*case(boxes, snapped))
    assert gate.status == "FAIL", gate.model_dump_json()
    assert "boundary" in gate.reason.lower()


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("side", (0, 1))
def test_smv_print_rounding_does_not_put_a_boundary_obstacle_outside_domain(axis, side):
    # Rounding outward at either boundary is below the existing 1e-7 SMV
    # coordinate tolerance. Integer cell indices still identify the boundary.
    offset = 0.12345002 if side == 0 else 0.12344998
    domain = [offset, offset + 1] * 3
    box = [offset + 0.4, offset + 0.6] * 3
    box[2 * axis + side] = domain[2 * axis + side]
    gate = effective_obstructions(*case({"wall": box}, {"wall": box}, domain))
    assert gate.status == "PASS", gate.model_dump_json()


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("side", (0, 1))
@pytest.mark.parametrize("offset", (0.12345002, 0.12344998))
def test_smv_print_rounding_cannot_hide_a_real_boundary_gap_closure(axis, side, offset):
    domain = [offset, offset + 1] * 3
    box = [offset + 0.4, offset + 0.6] * 3
    box[2 * axis + side] = offset + (0.04 if side == 0 else 0.96)
    snapped = box[:]
    snapped[2 * axis + side] = domain[2 * axis + side]
    gate = effective_obstructions(*case({"wall": box}, {"wall": snapped}, domain))
    assert gate.status == "FAIL", gate.model_dump_json()
    assert "boundary" in gate.reason.lower()


def test_smv_grid_rounding_beyond_supported_precision_remains_inconclusive():
    offset = 0.123452
    domain = [offset, offset + 1] * 3
    box = [offset, offset + 0.6, offset + 0.4, offset + 0.6, offset + 0.4, offset + 0.6]
    gate = effective_obstructions(*case({"wall": box}, {"wall": box}, domain))
    assert gate.status == "INCONCLUSIVE", gate.model_dump_json()
    assert "grid" in gate.reason.lower()


def test_source_outside_domain_is_not_clipped_by_smv_print_tolerance():
    source = [-2e-8, 0.6, 0.4, 0.6, 0.4, 0.6]
    snapped = [0, 0.6, 0.4, 0.6, 0.4, 0.6]
    gate = effective_obstructions(*case({"wall": source}, {"wall": snapped}))
    assert gate.status == "INCONCLUSIVE", gate.model_dump_json()
    assert "out-of-domain" in gate.reason.lower()


def test_diagonal_air_passage_closes_without_pairwise_face_overlap():
    boxes = {"a": [0, 0.48, 0, 0.48, 0, 1], "b": [0.52, 1, 0.52, 1, 0, 1]}
    snapped = {"a": [0, 0.5, 0, 0.5, 0, 1], "b": [0.5, 1, 0.5, 1, 0, 1]}
    gate = effective_obstructions(*case(boxes, snapped))
    assert gate.status == "FAIL", gate.reason
    assert gate.evidence["air_connectivity"]["source_components"] == 1
    assert gate.evidence["air_connectivity"]["effective_components"] == 2


def test_topology_resource_limit_is_inconclusive(monkeypatch):
    from ifc_to_fds.modules.verification.application import effective_topology

    monkeypatch.setattr(effective_topology, "CELL_BUDGET", 1)
    box = [0.1, 0.6, 0, 1, 0, 1]
    gate = effective_obstructions(*case({"wall": box}, {"wall": box}))
    assert gate.status == "INCONCLUSIVE"
    assert "budget" in gate.reason


def test_same_component_count_does_not_hide_a_split_and_a_merge():
    from ifc_to_fds.modules.verification.application.effective_topology import verify_air_paths

    # Both states divide the domain into three regions, with different membership.
    # Counting components alone would accept this change.
    source = {"a": [0.3, 0.4, 0, 1, 0, 1], "b": [0.7, 0.8, 0, 1, 0, 1]}
    actual = {"a": [0.5, 0.6, 0, 1, 0, 1], "b": source["b"]}
    gate = verify_air_paths(source, actual, [0, 1, 0, 1, 0, 1])
    assert gate.status == "FAIL"
    assert gate.evidence["source_components"] == gate.evidence["effective_components"] == 3
    assert len(gate.evidence["component_correspondence"]) == 4


def test_boundary_certificate_digest_covers_the_air_topology_checker(monkeypatch):
    from pathlib import Path
    from ifc_to_fds.modules.simulation.api import adapter_digest

    before = adapter_digest()
    original = Path.read_text

    def changed(path, *args, **kwargs):
        contents = original(path, *args, **kwargs)
        return contents + "\n# mutation\n" if path.name == "effective_topology.py" else contents

    monkeypatch.setattr(Path, "read_text", changed)
    assert adapter_digest() != before
