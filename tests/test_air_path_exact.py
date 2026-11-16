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


class _Unreadable:
    """An emitted primitive whose mesh cannot be built."""

    kind, id = "OBST", "BAD"

    def __init__(self, source):
        self.source = source

    def mesh(self):
        raise RuntimeError("mesh could not be built")


class _NoMesh(_Unreadable):
    """An emitted primitive that returns no mesh instead of raising."""

    def mesh(self):
        return None


def _with_unreadable(context, monkeypatch, source, primitive=_Unreadable):
    parsed = context.parsed
    emitted = list(parsed.primitives) + [primitive(source)]
    monkeypatch.setattr(type(parsed), "primitives", property(lambda self: emitted))  # `primitives` is computed
    return context


def test_an_unreadable_emitted_solid_makes_the_air_path_inconclusive_not_a_pass(box_model, monkeypatch):
    keys = frozenset(e.entity_key for e in box_model.elements)
    context = _with_unreadable(_context(box_model, keys), monkeypatch, source={})  # no source: it may block the envelope
    outcome = AirPathTopologyChecker().check(context)
    assert outcome.result.status == GateStatus.INCONCLUSIVE
    assert "BAD" in outcome.result.reason and outcome.metrics["air_path"]["unreadable_count"] == 1


def test_an_unreadable_solid_of_an_unrelated_source_is_not_held_against_the_enclosure(box_model, monkeypatch):
    keys = frozenset(e.entity_key for e in box_model.elements)
    context = _with_unreadable(_context(box_model, keys), monkeypatch, source={"entity_key": "elsewhere:999"})
    assert AirPathTopologyChecker().check(context).result.status == GateStatus.PASS


def test_equal_source_wall_does_not_claim_source_airtightness(box_model):
    """A source with only one wall can pass equality without enclosing a building."""
    keys = frozenset(e.entity_key for e in box_model.elements)
    outcome = AirPathTopologyChecker().check(_context(box_model, keys))

    assert outcome.result.status == GateStatus.PASS
    assert outcome.result.reason == (
        "Enclosure solids in the deck equal the source: all 1 proven equal to the IFC geometry. "
        "Source airtightness is not assessed by this gate."
    )
    assert "no leak" not in outcome.result.reason.lower()
    evidence = {"enclosure_count": 1, "method": "ALL_ENCLOSURES_PROVEN_EQUAL", "leak_volume_m3": 0.0}
    assert outcome.result.evidence == evidence
    assert outcome.metrics == {"air_path": evidence}
    assert outcome.findings == []


def test_an_emitted_solid_without_a_mesh_is_not_skipped_silently(box_model, monkeypatch):
    keys = frozenset(e.entity_key for e in box_model.elements)
    context = _with_unreadable(_context(box_model, keys), monkeypatch, source={}, primitive=_NoMesh)
    outcome = AirPathTopologyChecker().check(context)
    assert outcome.result.status == GateStatus.INCONCLUSIVE
    assert "BAD" in outcome.result.reason and outcome.metrics["air_path"]["unreadable_count"] == 1


def test_a_missing_mesh_of_an_unrelated_source_is_not_held_against_the_enclosure(box_model, monkeypatch):
    keys = frozenset(e.entity_key for e in box_model.elements)
    context = _with_unreadable(_context(box_model, keys), monkeypatch, source={"entity_key": "elsewhere:999"}, primitive=_NoMesh)
    assert AirPathTopologyChecker().check(context).result.status == GateStatus.PASS
