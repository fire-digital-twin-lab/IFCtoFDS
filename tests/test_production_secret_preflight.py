"""Regression quyền Linux host của file-backed Docker Compose secret."""

import importlib.util
import os
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production-secret-preflight.py"
SPEC = importlib.util.spec_from_file_location("ifctofds_secret_preflight", SOURCE)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


@pytest.mark.skipif(os.name != "posix", reason="Linux file ownership/mode policy")
def test_accepts_group_read_only_file_without_reading_secret(tmp_path, monkeypatch):
    secret = tmp_path / "api-key"
    secret.write_text("nonproduction-marker-do-not-print", encoding="utf-8")
    secret.chmod(0o640)

    # Preflight kiểm tra metadata, không yêu cầu quyền đọc nội dung.
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: pytest.fail("read secret"))
    preflight.inspect_secret_file(
        secret, expected_uid=os.getuid(), expected_gid=os.getgid()
    )


@pytest.mark.skipif(os.name != "posix", reason="Linux file ownership/mode policy")
@pytest.mark.parametrize("mode", [0o600, 0o644, 0o666, 0o777, 0o400])
def test_rejects_wrong_file_permission_modes(tmp_path, mode):
    secret = tmp_path / "api-key"
    secret.write_bytes(b"placeholder")
    secret.chmod(mode)
    with pytest.raises(preflight.SecretFilePolicyError, match="exactly 0640"):
        preflight.inspect_secret_file(
            secret, expected_uid=os.getuid(), expected_gid=os.getgid()
        )


@pytest.mark.skipif(os.name != "posix", reason="Linux file ownership/mode policy")
def test_rejects_wrong_owner_or_group(tmp_path):
    secret = tmp_path / "api-key"
    secret.write_bytes(b"placeholder")
    secret.chmod(0o640)
    with pytest.raises(preflight.SecretFilePolicyError, match="owner/group"):
        preflight.inspect_secret_file(
            secret, expected_uid=os.getuid() + 1, expected_gid=os.getgid()
        )
    with pytest.raises(preflight.SecretFilePolicyError, match="owner/group"):
        preflight.inspect_secret_file(
            secret, expected_uid=os.getuid(), expected_gid=os.getgid() + 1
        )


@pytest.mark.skipif(os.name != "posix", reason="Linux file ownership/mode policy")
def test_rejects_symlink_to_other_file(tmp_path):
    target = tmp_path / "real-key"
    target.write_bytes(b"placeholder")
    target.chmod(0o640)
    linked = tmp_path / "api-key"
    linked.symlink_to(target)
    with pytest.raises(preflight.SecretFilePolicyError, match="symbolic link"):
        preflight.inspect_secret_file(
            linked, expected_uid=os.getuid(), expected_gid=os.getgid()
        )


@pytest.mark.skipif(os.name != "posix", reason="Linux file ownership/mode policy")
def test_rejects_group_or_world_writable_parent(tmp_path):
    secret = tmp_path / "api-key"
    secret.write_bytes(b"placeholder")
    secret.chmod(0o640)
    tmp_path.chmod(0o777)
    with pytest.raises(preflight.SecretFilePolicyError, match="parent directory"):
        preflight.inspect_secret_file(
            secret, expected_uid=os.getuid(), expected_gid=os.getgid()
        )


@pytest.mark.skipif(os.name != "posix", reason="Linux file ownership/mode policy")
def test_rejects_nonregular_missing_and_relative_paths(tmp_path):
    with pytest.raises(preflight.SecretFilePolicyError, match="regular file"):
        preflight.inspect_secret_file(
            tmp_path, expected_uid=os.getuid(), expected_gid=os.getgid()
        )
    with pytest.raises(preflight.SecretFilePolicyError, match="Cannot stat"):
        preflight.inspect_secret_file(tmp_path / "missing")
    with pytest.raises(preflight.SecretFilePolicyError, match="absolute"):
        preflight.inspect_secret_file(Path("relative-api-key"))


@pytest.mark.skipif(os.name != "posix", reason="Linux file ownership/mode policy")
def test_rejects_symlinked_parent_directory(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    secret = real / "api-key"
    secret.write_bytes(b"placeholder")
    secret.chmod(0o640)
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(preflight.SecretFilePolicyError, match="parent directory"):
        preflight.inspect_secret_file(
            linked / "api-key", expected_uid=os.getuid(), expected_gid=os.getgid()
        )
