"""Fail-closed smoke probe for an already deployed IFCtoFDS instance."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _get(url: str, api_key: str | None = None) -> tuple[int, object]:
    headers = {"User-Agent": "IFCtoFDS-production-smoke/1"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    args = parser.parse_args(argv)

    base = args.base_url.rstrip("/")
    if not base.startswith("https://"):
        sys.stderr.write("production smoke requires an https:// base URL\n")
        return 2

    health_status, health = _get(base + "/api/health")
    if health_status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
        sys.stderr.write("public health probe failed\n")
        return 1

    scheduler_status, scheduler = _get(base + "/api/scheduler-health", args.api_key)
    if (
        scheduler_status != 200
        or not isinstance(scheduler, dict)
        or scheduler.get("status") != "ok"
    ):
        sys.stderr.write("authenticated scheduler health probe failed\n")
        return 1

    root_status, _ = _get(base + "/")
    if root_status != 200:
        sys.stderr.write("workbench root probe failed\n")
        return 1

    print("production smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
