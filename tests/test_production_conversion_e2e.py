"""Unit regression cho probe HTTPS production: URL, payload, provenance và verdict."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production-conversion-e2e.py"
SPEC = importlib.util.spec_from_file_location("ifctofds_production_conversion_e2e", SOURCE)
assert SPEC is not None and SPEC.loader is not None
e2e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e2e)


@pytest.mark.parametrize(
    "bad",
    [
        "http://example.org",
        "https://user:pass@example.org",
        "https://example.org/api",
        "https://example.org/?p=1",
        "https://example.org/#fragment",
    ],
)
def test_probe_requires_clean_https_origin(bad):
    with pytest.raises(e2e.E2EError, match="HTTPS origin"):
        e2e._origin(bad)


def test_probe_accepts_clean_https_origin_and_no_redirect():
    assert e2e._origin("https://ifctofds.example.org/") == "https://ifctofds.example.org"
    assert e2e._NoRedirects().redirect_request(
        None, None, 302, "Found", {}, "http://untrusted.example"
    ) is None


def test_probe_multipart_contains_real_fixture_bytes():
    fixture = SOURCE.parents[1] / "tests" / "baseline" / "fixtures" / "tiny.ifc"
    content_type, body = e2e._multipart_ifc(fixture)
    assert content_type.startswith("multipart/form-data; boundary=ifctofds-")
    assert b'name="files"; filename="tiny.ifc"' in body
    assert fixture.read_bytes() in body
    assert body.endswith(b"--\r\n")


def _result(jid="job123", simulation_status="INCONCLUSIVE"):
    return {
        "status": "MAPPING_VERIFIED",
        "simulation_status": simulation_status,
        "gates": {
            "source_inventory": {"status": "PASS"},
            "geometry": {"status": "PASS"},
        },
        "artifacts": {
            name: {"url": f"/api/jobs/{jid}/artifacts/{name}"}
            for name in ("manifest", "fds", "geometry")
        },
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://untrusted.example/api/jobs/job123/artifacts/fds",
        "//untrusted.example/api/jobs/job123/artifacts/fds",
        "/api/jobs/other/artifacts/fds",
        "/api/jobs/job123/artifacts/fds?download=1",
        "/api/jobs/job123/artifacts/fds#section",
    ],
)
def test_probe_rejects_external_or_changed_artifact_urls(url):
    result = _result()
    result["artifacts"]["fds"]["url"] = url
    with pytest.raises(e2e.E2EError, match="outside the allowed job path"):
        e2e._artifact_path("job123", result, "fds")


def test_probe_checks_mapping_artifact_bytes_and_scientific_verdict():
    result = _result()
    contents = {
        "/api/jobs/job123/artifacts/manifest": b'{"acceptance_status":"MAPPING_VERIFIED"}',
        "/api/jobs/job123/artifacts/fds": b"&HEAD CHID='tiny' /\n",
        "/api/jobs/job123/artifacts/geometry": b'{"elements":{}}',
    }

    class FakeAPI:
        def json(self, path):
            assert path == "/api/jobs/job123/result"
            return result

        def request(self, path):
            return 200, contents[path]

    evidence = e2e._evidence(FakeAPI(), "job123")
    assert evidence["mapping_status"] == "MAPPING_VERIFIED"
    assert evidence["simulation_status"] == "INCONCLUSIVE"
    assert evidence["artifact_sha256"]["fds"] == hashlib.sha256(
        contents["/api/jobs/job123/artifacts/fds"]
    ).hexdigest()

    result["simulation_status"] = "SIMULATION_VERIFIED"
    with pytest.raises(e2e.E2EError, match="scientific verification"):
        e2e._evidence(FakeAPI(), "job123")


def test_probe_rejects_malformed_manifest_and_invalid_mapping():
    result = _result()

    class FakeAPI:
        def json(self, path):
            return result

        def request(self, path):
            if path.endswith("/manifest"):
                return 200, json.dumps({"acceptance_status": "INCONCLUSIVE"}).encode()
            return 200, b"other"

    with pytest.raises(e2e.E2EError, match="Manifest acceptance status"):
        e2e._evidence(FakeAPI(), "job123")
    result["gates"]["geometry"]["status"] = "INCONCLUSIVE"
    with pytest.raises(e2e.E2EError, match="geometry mapping gate"):
        e2e._evidence(FakeAPI(), "job123")
