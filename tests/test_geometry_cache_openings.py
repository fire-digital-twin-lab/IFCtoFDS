"""A warm geometry cache must give the same opening records as a cold run (Duplex flake, roadmap A4.7)."""

import ifcopenshell
import ifcopenshell.api.root

from ifc_to_fds.core.compare import normalize
from ifc_to_fds.pipeline import prepare

COMPARED_AWAY = {"mesh", "bounding_box", "is_subtracted", "verification_status"}  # same exclusions as the audit


def test_openings_of_a_host_without_a_body_are_the_same_cold_and_warm(tiny_ifc, tmp_path, monkeypatch):
    path, file, wall = tiny_ifc
    opening = ifcopenshell.api.root.create_entity(file, ifc_class="IfcOpeningElement", name="Void")
    opening.ObjectPlacement = wall.ObjectPlacement
    file.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=wall,
        RelatedOpeningElement=opening,
    )
    wall.Representation = None  # no body: the geometry stage skips this host and its openings
    bodyless = tmp_path / "bodyless.ifc"
    file.write(str(bodyless))
    monkeypatch.setenv("IFCFDS_GEOMETRY_CACHE", str(tmp_path / "cache"))

    def records():
        model = prepare([str(bodyless)], {})
        return {
            e.entity_key: normalize([o.model_dump(mode="json", exclude=COMPARED_AWAY) for o in e.openings])
            for e in model.elements
            if e.openings
        }

    cold, warm = records(), records()
    assert cold and cold == warm
