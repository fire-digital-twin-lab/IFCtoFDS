"""air_path must not let Manifold's Boolean misjudge solids that the geometry gate proved equal."""

from pathlib import Path

from ifc_to_fds.domain.validation.model import GateStatus, ValidationContext
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.pipeline import convert
from ifc_to_fds.validation.checkers.air_path import AirPathTopologyChecker
from ifc_to_fds.validation.metrics import is_exact_match
from ifc_to_fds.validation.parser import parse_fds

FZK = str(Path(__file__).resolve().parents[1] / "examples" / "AC20-FZK-Haus.ifc")


def _context(model, exact=frozenset()):
    text, manifest = serialize_fds(model)
    return ValidationContext(model=model, fds_text=text, manifest=manifest, parsed_fds=parse_fds(text), exact_elements=exact)


def test_exactness_needs_every_criterion():
    ok = dict(surface_proven=True, solid_iou=1.0, relative_volume_error=0.0, reference_components=1, output_components=1)
    assert is_exact_match(ok)
    for change in (dict(surface_proven=False), dict(solid_iou=0.999), dict(relative_volume_error=1e-6), dict(output_components=2)):
        assert not is_exact_match({**ok, **change})


def test_proven_equal_enclosure_passes_without_boolean(box_model, monkeypatch):
    import ifc_to_fds.validation.checkers.air_path as ap

    keys = frozenset(e.entity_key for e in box_model.elements)
    monkeypatch.setattr(ap, "solid_boolean", lambda *a: (_ for _ in ()).throw(AssertionError("Boolean ran")))
    outcome = AirPathTopologyChecker().check(_context(box_model, keys))
    assert outcome.result.status == GateStatus.PASS
    assert outcome.metrics["air_path"]["method"] == "ALL_ENCLOSURES_PROVEN_EQUAL"


def test_unproven_enclosure_still_runs_the_boolean_check(box_model):
    outcome = AirPathTopologyChecker().check(_context(box_model))
    assert "method" not in outcome.metrics.get("air_path", {})


def test_fzk_box_covers_keep_air_path_pass(monkeypatch):
    """Regression for M2.1: a proven box cover of an FZK wall used to flip air_path to FAIL."""
    monkeypatch.setenv("IFCFDS_OBST_BOX_SETS", "1")
    gate = convert([FZK])["report"]["gates"]["air_path"]
    assert gate["status"] == "PASS", gate
