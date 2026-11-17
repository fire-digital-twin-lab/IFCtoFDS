"""The native iterator runs single-threaded unless asked otherwise: multi-threaded runs were not reproducible."""

import pytest

from ifc_to_fds.geometry import engine
from ifc_to_fds.core.inventory import extract_inventory


@pytest.mark.parametrize("value,expected", [
    (None, 1), ("1", 1), ("4", 4), ("0", 1), ("-3", 1), ("many", 1), ("", 1),
])
def test_geometry_threads_default_and_override(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("IFCFDS_GEOMETRY_THREADS", raising=False)
    else:
        monkeypatch.setenv("IFCFDS_GEOMETRY_THREADS", value)
    assert engine.geometry_threads() == expected


def test_process_model_geometry_passes_one_thread_to_iterator(tiny_ifc, monkeypatch):
    path, _, _ = tiny_ifc
    model, source = extract_inventory(str(path))
    monkeypatch.delenv("IFCFDS_GEOMETRY_THREADS", raising=False)
    iterator = engine.ifcopenshell.geom.iterator
    seen = []

    def spy(settings, ifc_file, threads, **kwargs):
        seen.append(threads)
        return iterator(settings, ifc_file, threads, **kwargs)

    monkeypatch.setattr(engine.ifcopenshell.geom, "iterator", spy)
    engine.process_model_geometry(model, source)
    assert seen == [1]
