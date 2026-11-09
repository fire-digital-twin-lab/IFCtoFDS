"""E2E conversion probe through a deployed HTTPS production Compose stack.

Only verifies software/runtime correctness. Never reports SIMULATION_VERIFIED.
All credentials are read from a file and never printed or serialized in evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


_TERMINAL = frozenset({"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"})
_EXPECTED_STATUS = "MAPPING_VERIFIED"
_MAX_RESPONSE_BYTES = 20 * 1024 * 1024


class E2EError(RuntimeError):
    """A production software acceptance contract was violated."""


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if not (
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
    ):
        raise E2EError("A credential-free HTTPS origin is required")
    return value.rstrip("/")


class API:
    def __init__(self, origin: str, api_key: str):
        self.origin = _origin(origin)
        if len(api_key) < 32 or any(char.isspace() for char in api_key):
            raise E2EError("Invalid API key file")
        self.api_key = api_key
        # Never forward credentials to an HTTP proxy or a redirect destination.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirects()
        )

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        authenticated: bool = True,
    ) -> tuple[int, bytes]:
        if not path.startswith("/api/") or any(c in path for c in ("?", "#", "\\")):
            raise E2EError("Invalid API path")
        outgoing = {"User-Agent": "IFCtoFDS-Production-E2E/1"}
        if authenticated:
            outgoing["X-API-Key"] = self.api_key
        outgoing.update(headers or {})
        req = urllib.request.Request(
            self.origin + path, data=body, headers=outgoing, method=method
        )
        try:
            response = self.opener.open(req, timeout=25)
        except urllib.error.HTTPError as exc:
            response = exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise E2EError("HTTPS request unavailable") from exc
        with response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise E2EError("Unexpectedly large API response")
            return response.code, raw

    def json(
        self, path: str, *, expected: int = 200
    ) -> dict:
        status, raw = self.request(path)
        if status != expected:
            raise E2EError(f"API contract failure ({path}): HTTP {status}")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise E2EError("Invalid JSON response") from exc
        if not isinstance(value, dict):
            raise E2EError("Expected JSON object")
        return value


def _multipart_ifc(path: Path) -> tuple[str, bytes]:
    if not path.is_file() or path.suffix.lower() != ".ifc":
        raise E2EError("A checked-in IFC fixture is required")
    payload = path.read_bytes()
    if not payload or len(payload) > 1024 * 1024:
        raise E2EError("CI IFC fixture size is outside expected limits")
    boundary = "ifctofds-" + secrets.token_hex(12)
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="tiny.ifc"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("ascii") + payload + f"\r\n--{boundary}--\r\n".encode("ascii")
    return f"multipart/form-data; boundary={boundary}", body


def _wait_healthy(api: API, seconds: int) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            status, _ = api.request("/api/health", authenticated=False)
            if status == 200:
                scheduler = api.json("/api/scheduler-health")
                if scheduler.get("status") == "ok":
                    return
        except E2EError:
            pass
        time.sleep(0.5)
    raise E2EError("Health/scheduler did not recover within the test deadline")


def _wait_completed(api: API, jid: str, seconds: int) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = api.json(f"/api/jobs/{jid}").get("state")
        if state in _TERMINAL:
            if state != "COMPLETED":
                raise E2EError(f"IFC conversion did not complete: {state}")
            return
        time.sleep(0.5)
    raise E2EError("Conversion job exceeded the E2E deadline")


def _artifact_path(jid: str, result: dict, key: str) -> str:
    try:
        raw = result["artifacts"][key]["url"]
    except (KeyError, TypeError) as exc:
        raise E2EError(f"Missing {key} artifact declaration") from exc
    if not isinstance(raw, str):
        raise E2EError("Artifact URL must be a string")
    parsed = urllib.parse.urlsplit(raw)
    expected = f"/api/jobs/{jid}/artifacts/{key}"
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.path != expected
    ):
        raise E2EError("Artifact URL is outside the allowed job path")
    return expected


def _evidence(api: API, jid: str) -> dict:
    result = api.json(f"/api/jobs/{jid}/result")
    if result.get("status") != _EXPECTED_STATUS:
        raise E2EError("Tiny IFC did not reach scoped MAPPING_VERIFIED")
    if result.get("simulation_status") != "INCONCLUSIVE":
        raise E2EError("Conversion unexpectedly asserted scientific verification")
    checks = result.get("gates", {})
    if any(checks.get(gate, {}).get("status") != "PASS" for gate in ("source_inventory", "geometry")):
        raise E2EError("Source inventory or geometry mapping gate did not pass")

    artifact_hashes = {}
    for key in ("manifest", "fds", "geometry"):
        path = _artifact_path(jid, result, key)
        status, content = api.request(path)
        if status != 200 or not content:
            raise E2EError(f"Missing or unreadable {key} artifact ({status})")
        artifact_hashes[key] = hashlib.sha256(content).hexdigest()
        if key == "manifest":
            try:
                manifest = json.loads(content.decode("utf-8"))
            except (UnicodeError, ValueError) as exc:
                raise E2EError("Manifest artifact is malformed") from exc
            if manifest.get("acceptance_status") != _EXPECTED_STATUS:
                raise E2EError("Manifest acceptance status differs from result")

    return {
        "schema": 1,
        "job_id": jid,
        "mapping_status": result["status"],
        "simulation_status": result["simulation_status"],
        "artifact_sha256": artifact_hashes,
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("create", "verify"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-file", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--job-timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.job_timeout <= 300:
            raise E2EError("Job timeout must be between 1 and 300 seconds")
        api = API(args.base_url, args.api_key_file.read_text(encoding="utf-8").strip())
        _wait_healthy(api, 60)
        if args.phase == "create":
            if args.fixture is None or args.evidence.exists():
                raise E2EError("Create requires an IFC fixture and a new evidence path")
            content_type, payload = _multipart_ifc(args.fixture)
            bad_auth, _ = api.request(
                "/api/jobs", method="POST", body=payload,
                headers={"Content-Type": content_type}, authenticated=False,
            )
            if bad_auth != 401:
                raise E2EError("Unauthenticated job submission was not rejected")
            bad_origin, _ = api.request(
                "/api/jobs", method="POST", body=payload,
                headers={"Content-Type": content_type, "Origin": "https://untrusted.example"},
            )
            if bad_origin != 403:
                raise E2EError("Untrusted Origin job submission was not rejected")
            status, raw = api.request(
                "/api/jobs", method="POST", body=payload,
                headers={"Content-Type": content_type},
            )
            if status != 202:
                raise E2EError(f"Authenticated IFC job submission failed: HTTP {status}")
            try:
                jid = json.loads(raw.decode("utf-8"))["id"]
            except (ValueError, UnicodeError, KeyError, TypeError) as exc:
                raise E2EError("Job admission did not return an ID") from exc
            if not isinstance(jid, str) or not jid or "/" in jid:
                raise E2EError("Invalid job ID")
            _wait_completed(api, jid, args.job_timeout)
            evidence = _evidence(api, jid)
            evidence["fixture_sha256"] = hashlib.sha256(args.fixture.read_bytes()).hexdigest()
            args.evidence.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
            print("Production IFC conversion E2E: CREATE PASS (software only)")
        else:
            evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
            if evidence.get("schema") != 1:
                raise E2EError("Unexpected evidence schema")
            jid = evidence.get("job_id")
            if not isinstance(jid, str) or not jid or "/" in jid:
                raise E2EError("Invalid persisted job ID")
            state = api.json(f"/api/jobs/{jid}")
            if state.get("state") != "COMPLETED":
                raise E2EError("Job state was not durable across container restart")
            actual = _evidence(api, jid)
            if actual != {
                key: evidence[key]
                for key in ("schema", "job_id", "mapping_status", "simulation_status", "artifact_sha256")
            }:
                raise E2EError("Artifact evidence changed after container restart")
            print("Production IFC conversion E2E: RESTART/PERSISTENCE PASS (software only)")
        return 0
    except (E2EError, OSError, ValueError, KeyError) as exc:
        # Deliberately avoid traceback or credential/body dumps in CI logs.
        print(f"Production conversion E2E: FAIL ({type(exc).__name__})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
