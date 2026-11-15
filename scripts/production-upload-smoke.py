"""Fail-closed HTTPS probe that a deployed instance accepts a large multi-file upload (plan M5.1).

The files are zero padding behind a STEP header, so the job is cancelled and purged; only the upload path is
exercised. A 2 x 150 MiB body does not fit the 256 MiB /tmp tmpfs of the compose app once it is parsed, so
success proves TMPDIR points at the jobs volume.
"""

from __future__ import annotations

import argparse
import http.client
import json
import ssl
import sys
import urllib.parse
from pathlib import Path

CHUNK = b"\0" * (1 << 20)


def multipart(files: int, mib: int, boundary: str = "ifcfdsUploadSmoke"):
    """(content length, chunk iterator) of a streamed multipart body with `files` uploads of `mib` MiB."""
    def head(i):
        return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
                f"filename=\"big-{i}.ifc\"\r\nContent-Type: application/octet-stream\r\n\r\n"
                "ISO-10303-21;\r\n").encode()

    tail = f"\r\n--{boundary}--\r\n".encode()
    crlf = b"\r\n"
    length = sum(len(head(i)) + mib * len(CHUNK) + (len(crlf) if i < files - 1 else 0) for i in range(files)) + len(tail)

    def chunks():
        for i in range(files):
            yield head(i)
            for _ in range(mib):
                yield CHUNK
            if i < files - 1:
                yield crlf
        yield tail

    return length, chunks()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-file", required=True)
    parser.add_argument("--files", type=int, default=2)
    parser.add_argument("--mib", type=int, default=150)
    args = parser.parse_args(argv)
    url = urllib.parse.urlsplit(args.base_url.rstrip("/"))
    if url.scheme != "https" or not url.hostname or url.path or url.username:
        sys.stderr.write("upload smoke requires an HTTPS origin without credentials or a path\n")
        return 2
    try:
        key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        key = ""
    if not key:
        sys.stderr.write("cannot read a non-empty API key file\n")
        return 2

    def call(method, path, body=None, headers=None):
        conn = http.client.HTTPSConnection(url.hostname, url.port or 443, timeout=600, context=ssl.create_default_context())
        try:
            conn.request(method, path, body=body, headers={"X-API-Key": key, **(headers or {})})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    length, body = multipart(args.files, args.mib)
    status, raw = call("POST", "/api/jobs", body, {
        "Content-Type": "multipart/form-data; boundary=ifcfdsUploadSmoke", "Content-Length": str(length)})
    if status != 202:
        sys.stderr.write(f"large upload rejected with HTTP {status}: {raw[:200]!r}\n")
        return 1
    jid = json.loads(raw)["id"]
    call("POST", f"/api/jobs/{jid}/cancel")
    call("DELETE", f"/api/jobs/{jid}?purge=true")
    print(f"upload smoke: PASS ({args.files} x {args.mib} MiB accepted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
