"""`serve` prepares TMPDIR on the jobs volume so large uploads never spill into the small /tmp tmpfs."""

import sys
import types

from ifc_to_fds.cli import main


def serve(monkeypatch, tmp_path, tmpdir):
    calls = []
    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(run=lambda *a, **k: calls.append(k)))
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    code = main(["serve", "--host", "127.0.0.1", "--port", "8001"])
    return code, calls


def test_spool_directory_is_created_and_leftovers_are_cleared(monkeypatch, tmp_path):
    spool = tmp_path / "jobs" / ".upload-tmp"
    code, calls = serve(monkeypatch, tmp_path, spool)
    assert code == 0 and spool.is_dir() and calls
    (spool / "tmpleft.bin").write_bytes(b"x")
    serve(monkeypatch, tmp_path, spool)
    assert spool.is_dir() and not list(spool.iterdir())


def test_other_directories_are_never_cleared(monkeypatch, tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "keep.bin").write_bytes(b"x")
    serve(monkeypatch, tmp_path, shared)
    assert (shared / "keep.bin").exists()


def test_unusable_spool_refuses_to_start(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    code, calls = serve(monkeypatch, tmp_path, blocker / ".upload-tmp")
    assert code == 1 and not calls
