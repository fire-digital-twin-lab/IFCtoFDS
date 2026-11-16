"""M6.F5: a Windows output folder that is too deep is refused before conversion, with a clear message."""

from pathlib import Path

import pytest

from ifc_to_fds.adapters.storage import path_budget
from ifc_to_fds.adapters.storage.path_budget import check_output_path_budget, longest_artifact_path

TINY = str(Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc")


def _root(length, base="/r"):
    """A fake output folder whose full path is exactly `length` characters (it is never created)."""
    return base + "/" + "d" * (length - len(base) - 1)


def test_the_longest_payload_path_is_the_one_to_check(tmp_path):
    longest = longest_artifact_path(tmp_path / "model.fds")
    assert longest.name.endswith(".bin") and len(longest.name) == 68
    assert longest.parent.name == "model_geometry.payloads" or longest.parent.name.endswith("_geometry.payloads")


def test_a_deep_folder_is_refused_when_long_paths_are_off():
    deep = _root(170) + "/tiny.fds"
    with pytest.raises(ValueError, match=r"too deep.*characters.*LongPathsEnabled.*nothing was written"):
        check_output_path_budget(deep, limit=260, long_paths=False)


def test_a_short_folder_and_a_system_with_long_paths_are_accepted():
    check_output_path_budget(_root(60) + "/tiny.fds", limit=260, long_paths=False)
    check_output_path_budget(_root(400) + "/tiny.fds", limit=260, long_paths=True)


def test_the_limit_is_exact_at_the_boundary():
    base = len(str(longest_artifact_path(_root(100) + "/tiny.fds")))  # path length for a 100-character folder
    check_output_path_budget(_root(100) + "/tiny.fds", limit=base + 1, long_paths=False)
    with pytest.raises(ValueError):
        check_output_path_budget(_root(100) + "/tiny.fds", limit=base, long_paths=False)


def test_the_staging_name_is_short_enough_to_leave_room():
    # 32 hex characters used to cost 20 more characters per folder level than needed
    assert path_budget.UNIQUE_HEX == 12 and len(path_budget.STAGING_PREFIX) + path_budget.UNIQUE_HEX < 25


def test_a_refused_conversion_writes_nothing_and_exits_with_a_message(tmp_path, monkeypatch, capsys):
    from ifc_to_fds.cli import main

    monkeypatch.setattr(path_budget, "long_paths_enabled", lambda: False)
    monkeypatch.setattr("ifc_to_fds.cli.check_output_path_budget", lambda output: path_budget.check_output_path_budget(output, limit=40, long_paths=False))
    target = tmp_path / "out" / "tiny.fds"
    assert main(["convert", TINY, "-o", str(target)]) == 3
    assert "too deep" in capsys.readouterr().err
    assert not target.parent.exists() or not any(target.parent.iterdir())


def test_an_existing_bundle_is_not_touched_when_the_path_is_refused(tmp_path, monkeypatch):
    from ifc_to_fds.pipeline import convert, save_artifacts

    target = tmp_path / "keep" / "tiny.fds"
    result = convert([TINY], output_directory=tmp_path / "w1")
    save_artifacts(result, target)
    before = {p.name: p.read_bytes() for p in target.parent.iterdir() if p.is_file()}
    monkeypatch.setattr("ifc_to_fds.adapters.storage.filesystem.check_output_path_budget",
                        lambda output: path_budget.check_output_path_budget(output, limit=40, long_paths=False))
    with pytest.raises(ValueError, match="too deep"):
        save_artifacts(result, target)
    assert {p.name: p.read_bytes() for p in target.parent.iterdir() if p.is_file()} == before
    assert not list(target.parent.glob(".staging-*"))
