"""Kiểm tra quyền file-backed Compose secret trên Linux trước triển khai.

Chỉ kiểm tra metadata: tuyệt đối không đọc/in nội dung API key. Không thay thế
kiểm thử quyền đọc thực tế trong container hoặc chính sách quản trị secret.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat


class SecretFilePolicyError(ValueError):
    """File/đường dẫn secret không tuân thủ policy Linux host."""


def inspect_secret_file(
    path: Path,
    *,
    expected_uid: int = 0,
    expected_gid: int = 10001,
) -> None:
    """Bắt buộc regular file, owner/group được chọn, mode 0640; không có symlink."""
    if not path.is_absolute():
        raise SecretFilePolicyError("API key path must be absolute")
    if path.is_symlink():
        raise SecretFilePolicyError("API key file must not be a symbolic link")
    if path.parent.is_symlink():
        raise SecretFilePolicyError("API key parent directory must not be a symlink")

    try:
        meta = path.stat()
        parent_meta = path.parent.stat()
    except OSError as exc:
        raise SecretFilePolicyError("Cannot stat API key file or parent directory") from exc

    if not stat.S_ISREG(meta.st_mode):
        raise SecretFilePolicyError("API key must be a regular file")
    if meta.st_uid != expected_uid or meta.st_gid != expected_gid:
        raise SecretFilePolicyError("API key owner/group must match the deployment policy")
    if stat.S_IMODE(meta.st_mode) != 0o640:
        raise SecretFilePolicyError("API key permissions must be exactly 0640")
    if not stat.S_ISDIR(parent_meta.st_mode):
        raise SecretFilePolicyError("API key parent must be a directory")
    if parent_meta.st_mode & 0o022:
        raise SecretFilePolicyError("API key parent directory is writable by group/others")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra quyền Compose API key file")
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        inspect_secret_file(args.file)
    except SecretFilePolicyError as exc:
        parser.exit(1, f"Secret preflight: FAIL: {exc}\n")
    print("Secret preflight: PASS (metadata only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
