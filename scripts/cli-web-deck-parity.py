"""The CLI and the web API must produce the same FDS deck from the same IFC (plan M5.5).

    python scripts/cli-web-deck-parity.py --ifc <model.ifc> [--storey ID ...] --work <empty dir> --evidence <out.json>

Converts with `python -m ifc_to_fds convert`, then through a real server (`POST /api/jobs`), and compares the
SHA-256 of both `model.fds` files and the verdicts. When the decks differ it prints, to the terminal only, the
count and kinds of differing lines. The evidence file holds hashes, sizes and verdicts, never element names.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import runpy
import subprocess
import sys
import time
from pathlib import Path

drill = runpy.run_path(str(Path(__file__).with_name("long-job-drill.py")))
Server, wait_state = drill["Server"], drill["wait_state"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc", required=True, type=Path)
    parser.add_argument("--storey", action="append", default=[])
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--timeout-s", type=int, default=1800)
    args = parser.parse_args(argv)
    if args.work.exists() and any(args.work.iterdir()):
        sys.stderr.write("--work must be empty\n")
        return 2
    args.work.mkdir(parents=True, exist_ok=True)

    cli_deck = args.work / "cli" / "model.fds"
    started = time.monotonic()
    command = [sys.executable, "-m", "ifc_to_fds", "convert", str(args.ifc), "-o", str(cli_deck)]
    for storey in args.storey:
        command += ["--storey", storey]
    run = subprocess.run(command, capture_output=True, text=True, env={**__import__("os").environ, "IFCFDS_SOLVER_AUTODISCOVERY": "0",
                                                                      "IFCFDS_GEOMETRY_CACHE": str(args.work / "cache-cli")})
    cli_seconds = round(time.monotonic() - started, 1)
    if not cli_deck.is_file():
        sys.stderr.write(f"CLI produced no deck (exit {run.returncode}): {run.stderr[-300:]}\n")
        return 1
    cli_bytes = cli_deck.read_bytes()

    server = Server(args.work / "jobs", args.work / "cache-web", {})
    try:
        started = time.monotonic()
        status, job = server.submit(args.ifc, {"scope": {"storeys": args.storey}} if args.storey else None)
        assert status == 202, (status, job)
        final = wait_state(server, job["id"], {"COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"}, args.timeout_s)
        web_seconds = round(time.monotonic() - started, 1)
        status, web_bytes = server.call("GET", f"/api/jobs/{job['id']}/artifacts/fds")
        if isinstance(web_bytes, (dict, list)):  # the call helper decodes JSON; a deck is text
            web_bytes = json.dumps(web_bytes).encode()
        result_status, result = server.call("GET", f"/api/jobs/{job['id']}/result")
    finally:
        server.kill()
    if status != 200 or not isinstance(web_bytes, bytes):
        sys.stderr.write(f"web deck not available: job {final['state']}, HTTP {status}\n")
        return 1

    identical = cli_bytes == web_bytes
    evidence = {
        "ifc_bytes": args.ifc.stat().st_size, "storeys": len(args.storey),
        "cli": {"seconds": cli_seconds, "deck_bytes": len(cli_bytes), "sha256": sha256(cli_bytes)},
        "web": {"seconds": web_seconds, "state": final["state"], "deck_bytes": len(web_bytes), "sha256": sha256(web_bytes),
                "verdict": result.get("status") if isinstance(result, dict) else None},
        "identical": identical,
    }
    if not identical:
        a, b = cli_bytes.decode("utf-8", "replace").splitlines(), web_bytes.decode("utf-8", "replace").splitlines()
        changed = [line for line in difflib.unified_diff(a, b, lineterm="", n=0) if line[:1] in "+-" and line[:3] not in ("+++", "---")]
        evidence["differing_lines"] = len(changed)
        for line in changed[:6]:
            print(line[:160])
    args.evidence.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
