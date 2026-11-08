"""Extract the pinned official Windows bundle locally, without system installation."""

import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import zipfile

URL = "https://github.com/firemodels/fds/releases/download/FDS-6.11.1/FDS-6.11.1_SMV-6.11.2_win.exe"
ARCHIVE_SHA = "302ec837caaea8cb990cece085bee2284a0338d64fac0b77d46749a92ab12dfc"
BINARY_SHA = "dfaf04f1d46dbad77969b1cdd17baaa02a7aa6d63f46e96e93b9d9e635452b55"
DOWNLOAD_TIMEOUT_S = 90
RETRY_DELAYS_S = (1.0, 2.0, 4.0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or 500 <= exc.code <= 599
    return isinstance(exc, (urllib.error.URLError, TimeoutError))


def _download_archive(archive: Path) -> None:
    """Download through a temporary file; retry only transient transport failures."""

    part = archive.with_name(archive.name + ".part")
    last_error: BaseException | None = None
    for attempt in range(len(RETRY_DELAYS_S) + 1):
        part.unlink(missing_ok=True)
        try:
            request = urllib.request.Request(
                URL,
                headers={"User-Agent": "IFCtoFDS-pinned-FDS-installer"},
            )
            with urllib.request.urlopen(
                request,
                timeout=DOWNLOAD_TIMEOUT_S,
            ) as response, part.open("wb") as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(chunk)
            if _sha256(part) != ARCHIVE_SHA:
                raise ValueError("Official bundle differs from pinned checksum")
            part.replace(archive)
            return
        except BaseException as exc:
            part.unlink(missing_ok=True)
            if isinstance(exc, ValueError) or not _retryable(exc):
                raise
            last_error = exc
            if attempt >= len(RETRY_DELAYS_S):
                break
            time.sleep(RETRY_DELAYS_S[attempt])
    raise RuntimeError(
        "Could not download pinned FDS bundle after transient failures"
    ) from last_error


def install(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive = root / URL.rsplit("/", 1)[1]
    if archive.exists() and _sha256(archive) != ARCHIVE_SHA:
        archive.unlink()
    if not archive.exists():
        _download_archive(archive)
    if _sha256(archive) != ARCHIVE_SHA:
        raise ValueError("Official bundle differs from pinned checksum")
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not name.startswith("firemodels/FDS6/bin/"):
                continue
            if not (root / name).resolve().is_relative_to(root):
                raise ValueError("Unsafe archive path")
            bundle.extract(name, root)
    binary = root / "firemodels/FDS6/bin/fds_openmp.exe"
    if _sha256(binary) != BINARY_SHA:
        raise ValueError("Pinned binary checksum differs")
    (root / "installation.json").write_text(
        json.dumps(
            dict(
                version="6.11.1",
                url=URL,
                archive_sha256=ARCHIVE_SHA,
                binary=str(binary),
                binary_sha256=BINARY_SHA,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    return binary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".deps/fds-6.11.1")
    print(install(parser.parse_args().output))
