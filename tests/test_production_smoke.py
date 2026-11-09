"""Production smoke regression: HTML workbench and credential-safe HTTPS probes."""

import importlib.util
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production-smoke.py"
SPEC = importlib.util.spec_from_file_location("ifctofds_production_smoke", SOURCE)
assert SPEC is not None and SPEC.loader is not None
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class _Response:
    def __init__(self, status, content):
        self.status = status
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.content


def _stub_opener(monkeypatch, *, scheduler_html=False):
    requested = []

    class _Opener:
        def open(self, request, timeout):
            requested.append(request)
            assert timeout == 10
            path = request.full_url.split(".org", 1)[1]
            if path == "/api/health":
                return _Response(200, b'{"status":"ok"}')
            if path == "/api/scheduler-health":
                payload = b"<html>bad</html>" if scheduler_html else b'{"status":"ok"}'
                return _Response(200, payload)
            if path == "/":
                return _Response(200, b"<!doctype html><html>Workbench</html>")
            raise AssertionError(path)

    monkeypatch.setattr(smoke.urllib.request, "build_opener", lambda *_: _Opener())
    return requested


def test_smoke_accepts_html_workbench_without_json_parsing(tmp_path, monkeypatch, capsys):
    requests = _stub_opener(monkeypatch)
    secret = "test-nonproduction-key-do-not-leak"
    keyfile = tmp_path / "secret"
    keyfile.write_text(secret, encoding="utf-8")
    assert smoke.main(["--base-url", "https://example.org", "--api-key-file", str(keyfile)]) == 0
    assert [req.full_url for req in requests] == [
        "https://example.org/api/health",
        "https://example.org/api/scheduler-health",
        "https://example.org/",
    ]
    assert requests[1].get_header("X-api-key") == secret
    assert requests[2].get_header("X-api-key") is None
    captured = capsys.readouterr()
    assert "production smoke: PASS" in captured.out
    assert secret not in captured.out + captured.err


def test_smoke_rejects_non_json_scheduler_body(tmp_path, monkeypatch):
    _stub_opener(monkeypatch, scheduler_html=True)
    keyfile = tmp_path / "secret"
    keyfile.write_text("test-key", encoding="utf-8")
    assert smoke.main(["--base-url", "https://example.org", "--api-key-file", str(keyfile)]) == 1


def test_smoke_rejects_http_and_url_credentials(tmp_path):
    keyfile = tmp_path / "secret"
    keyfile.write_text("test-key", encoding="utf-8")
    for base in ("http://example.org", "https://user:pass@example.org", "https://example.org/prefix"):
        assert smoke.main(["--base-url", base, "--api-key-file", str(keyfile)]) == 2


def test_smoke_rejects_missing_api_key_file(tmp_path):
    assert smoke.main([
        "--base-url", "https://example.org", "--api-key-file", str(tmp_path / "missing")
    ]) == 2


def test_redirect_handler_never_follows_redirect():
    assert smoke._NoRedirects().redirect_request(
        None, None, 302, "Found", None, "http://untrusted.example"
    ) is None
