"""Extract the pinned official Windows bundle locally, without system installation."""

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

URL = "https://github.com/firemodels/fds/releases/download/FDS-6.11.1/FDS-6.11.1_SMV-6.11.2_win.exe"
ARCHIVE_SHA = "302ec837caaea8cb990cece085bee2284a0338d64fac0b77d46749a92ab12dfc"
BINARY_SHA = "dfaf04f1d46dbad77969b1cdd17baaa02a7aa6d63f46e96e93b9d9e635452b55"


def install(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive = root / URL.rsplit("/", 1)[1]
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Official bundle differs from pinned checksum")
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not name.startswith("firemodels/FDS6/bin/"):
                continue
            if not (root / name).resolve().is_relative_to(root):
                raise ValueError("Unsafe archive path")
            bundle.extract(name, root)
    binary = root / "firemodels/FDS6/bin/fds_openmp.exe"
    if hashlib.sha256(binary.read_bytes()).hexdigest() != BINARY_SHA:
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
