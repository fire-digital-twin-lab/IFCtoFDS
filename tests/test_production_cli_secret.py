"""Fail-closed CLI semantics when --api-key-file is explicitly selected."""

import os

from ifc_to_fds.cli import main


def test_empty_file_does_not_fallback_to_existing_environment_key(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("IFCFDS_API_KEY", "stale-key-" + "a" * 40)
    path = tmp_path / "api-key"
    path.write_text(" \n", encoding="utf-8")

    assert main(["serve", "--host", "0.0.0.0", "--api-key-file", str(path)]) == 1
    captured = capsys.readouterr()
    assert "file is empty" in captured.err
    assert "stale-key" not in captured.out + captured.err


def test_missing_file_does_not_fallback_to_environment_key(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("IFCFDS_API_KEY", "stale-key-" + "b" * 40)
    path = tmp_path / "missing"
    assert main(["serve", "--host", "0.0.0.0", "--api-key-file", str(path)]) == 1
    captured = capsys.readouterr()
    assert "missing or not a regular file" in captured.err
    assert "stale-key" not in captured.out + captured.err


def test_invalid_utf8_file_is_rejected_without_logging_content(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "api-key"
    path.write_bytes(b"\xff\xfeprivate-not-valid-utf8")
    assert main(["serve", "--host", "0.0.0.0", "--api-key-file", str(path)]) == 1
    captured = capsys.readouterr()
    assert "Cannot read API key file" in captured.err
    assert "private-not-valid-utf8" not in captured.out + captured.err


def test_rejects_ambiguous_key_file_and_inline_key(tmp_path, capsys):
    path = tmp_path / "api-key"
    path.write_text("a" * 40, encoding="utf-8")
    assert main([
        "serve", "--host", "0.0.0.0",
        "--api-key-file", str(path), "--api-key", "b" * 40
    ]) == 1
    assert "not both" in capsys.readouterr().err


def test_valid_file_overrides_stale_environment_key_without_echo(
    tmp_path, monkeypatch, capsys
):
    import uvicorn

    secret = "c" * 40
    path = tmp_path / "api-key"
    path.write_text(secret + "\n", encoding="utf-8")
    monkeypatch.setenv("IFCFDS_API_KEY", "stale-key-" + "a" * 40)
    monkeypatch.setenv("IFCFDS_ALLOWED_HOSTS", "test.example.org")
    monkeypatch.setenv("IFCFDS_ENV", "production")
    called = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: called.append((args, kwargs)))

    assert main(["serve", "--host", "0.0.0.0", "--api-key-file", str(path)]) == 0
    assert os.environ["IFCFDS_API_KEY"] == secret
    assert len(called) == 1
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
