"""Fail-closed HTTPS smoke probe for an already deployed IFCtoFDS instance."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Do not follow redirects, especially ones that could expose API credentials."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get(url: str, api_key: str | None = None, *, expect_json: bool = True) -> tuple[int, object]:
    headers = {"User-Agent": "IFCtoFDS-production-smoke/1"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.build_opener(_NoRedirects()).open(request, timeout=10) as response:
            body = response.read()
            if not expect_json:
                return response.status, None
            try:
                return response.status, json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeError):
                return response.status, None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-file", required=True)
    args = parser.parse_args(argv)

    base = args.base_url.rstrip("/")
    try:
        parsed = urllib.parse.urlsplit(base)
        valid_base = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.path == ""
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid_base = False
    if not valid_base:
        sys.stderr.write("production smoke requires an HTTPS origin without credentials or a path\n")
        return 2

    try:
        api_key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        sys.stderr.write("cannot read production smoke API key file\n")
        return 2
    if not api_key:
        sys.stderr.write("production smoke API key file is empty\n")
        return 2

    health_status, health = _get(base + "/api/health")
    if health_status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
        sys.stderr.write("public health probe failed\n")
        return 1

    scheduler_status, scheduler = _get(base + "/api/scheduler-health", api_key)
    if (
        scheduler_status != 200
        or not isinstance(scheduler, dict)
        or scheduler.get("status") != "ok"
    ):
        sys.stderr.write("authenticated scheduler health probe failed\n")
        return 1

    root_status, _ = _get(base + "/", expect_json=False)
    if root_status != 200:
        sys.stderr.write("workbench root probe failed\n")
        return 1

    print("production smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
