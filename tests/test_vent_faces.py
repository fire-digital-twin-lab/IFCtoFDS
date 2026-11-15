"""M6.F2: a VENT may only sit on a solid/gas face of the OBST boxes that are actually written."""

import pytest

from ifc_to_fds.mapping.obst_boxes import vent_rests_on_solid_face

# Audit F2: a wall with a 1.0 x 2.1 m door cut, written as two boxes. Gas fills x 0..1, z 0..2.1 at y 0..0.3.
WALL = [(0, 4, 0, 0.3, 2.1, 3), (1, 4, 0, 0.3, 0, 2.1)]


def test_a_vent_inside_the_doorway_has_no_face_to_sit_on():
    assert not vent_rests_on_solid_face([0.2, 0.8, 0, 0, 0.8, 1.2], WALL)  # y=0 plane: only the boxes' front faces


def test_a_vent_on_the_solid_front_face_is_accepted():
    assert vent_rests_on_solid_face([2.0, 2.6, 0, 0, 0.8, 1.2], WALL)
    assert vent_rests_on_solid_face([2.0, 2.6, 0.3, 0.3, 0.8, 1.2], WALL)  # and on the back face


def test_a_vent_spanning_two_boxes_of_the_same_face_is_accepted():
    assert vent_rests_on_solid_face([0.5, 2.5, 0, 0, 2.3, 2.9], WALL)  # above the door: one box
    assert vent_rests_on_solid_face([1.5, 3.0, 0, 0, 1.8, 2.4], WALL)  # straddles the 2.1 m seam: both boxes, same y=0 face


def test_a_vent_half_over_the_doorway_is_refused():
    assert not vent_rests_on_solid_face([0.5, 1.5, 0, 0, 0.8, 1.2], WALL)


def test_the_plane_between_two_touching_boxes_is_not_an_interface():
    stacked = [(0, 2, 0, 1, 0, 1), (0, 2, 0, 1, 1, 2)]  # z=1 is inside the solid
    assert not vent_rests_on_solid_face([0.5, 1.5, 0.2, 0.8, 1, 1], stacked)
    assert vent_rests_on_solid_face([0.5, 1.5, 0.2, 0.8, 2, 2], stacked)  # the real top face


def test_a_vent_in_open_space_or_without_boxes_is_refused():
    assert not vent_rests_on_solid_face([5, 6, 0, 0, 0, 1], WALL)
    assert not vent_rests_on_solid_face([0, 1, 0, 0, 0, 1], [])


@pytest.mark.parametrize("axis_vent", [[1.0, 1.0, 0.2, 0.8, 0.2, 0.8], [0.2, 0.8, 1.0, 1.0, 0.2, 0.8], [0.2, 0.8, 0.2, 0.8, 1.0, 1.0]])
def test_every_axis_is_handled(axis_vent):
    cube = [(0, 1, 0, 1, 0, 1)]
    assert vent_rests_on_solid_face(axis_vent, cube)


# --- wiring: the compiler and the exporter use the same boxes ------------------------------------------------

from tests.test_hvac_network import connected_ifc  # noqa: E402,F401  (fixture)


def _vent_model(connected_ifc, monkeypatch, boxes):
    from ifc_to_fds.mapping.policy import plan_mapping
    from ifc_to_fds.pipeline import prepare

    path, config = connected_ifc
    # patched first: plan_mapping itself compiles the network, so a late patch would test nothing
    monkeypatch.setattr("ifc_to_fds.mep.network.emitted_obst_boxes", lambda element: boxes if element.ifc_type == "IfcWall" else [])
    model = prepare([str(path)], config)
    for decision in config["decisions"].values():
        for port, endpoint in decision["hvac"]["endpoints"].items():
            original = next(p for e in model.elements for p in e.ports if p.port_key == port)
            if original.world_position[0] == 1:
                endpoint.update(kind="VENT", vent_xb=[1, 1, 1, 1.4, 2, 2.3])
    return model, lambda: plan_mapping(model, decisions=config["decisions"])


def test_the_compiler_accepts_a_vent_on_a_written_box_face(connected_ifc, monkeypatch):
    from ifc_to_fds.mep.network import build_hvac_network

    model, plan_it = _vent_model(connected_ifc, monkeypatch, [(0, 1, 0, 4, 0, 4)])
    plan_it()
    assert any(node.boundary and node.boundary.kind == "VENT" for node in build_hvac_network(model).nodes)


def test_the_compiler_refuses_a_vent_over_a_doorway_and_names_the_port(connected_ifc, monkeypatch):
    from ifc_to_fds.mep.network import build_hvac_network

    doorway = [(0, 1, 0, 0.8, 0, 4), (0, 1, 1.6, 4, 0, 4)]  # gap at y 0.8..1.6 holds the 1.0..1.4 vent
    _, plan_it = _vent_model(connected_ifc, monkeypatch, doorway)
    with pytest.raises(ValueError, match=r"HVAC vent of ports .+ covers open space"):
        plan_it()


def test_the_exporter_writes_exactly_the_boxes_the_compiler_checks():
    from pathlib import Path

    from ifc_to_fds.mapping.obst_boxes import emitted_obst_boxes
    from ifc_to_fds.pipeline import convert, prepare
    from ifc_to_fds.validation.parser import parse_fds

    opening = str(Path(__file__).parent / "baseline" / "fixtures" / "opening.ifc")
    result = convert([opening])
    written = sorted(tuple(r.values["XB"]) for r in parse_fds(result["fds_text"]).records if r.kind == "OBST")
    model = prepare([opening], result["configuration"])
    wall = next(e for e in model.elements if e.ifc_type == "IfcWall")
    from ifc_to_fds.mapping.policy import plan_mapping

    plan_mapping(model)
    expected = sorted(tuple(map(float, b)) for b in emitted_obst_boxes(wall))
    assert len(written) == len(expected) == 2
    assert [tuple(round(v, 9) for v in box) for box in written] == [
        tuple(round(v, 9) for v in box) for box in expected
    ]
