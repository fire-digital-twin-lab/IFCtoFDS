"""Regression for explicit, fail-closed staging and production startup."""

import os
import subprocess
import sys

import pytest

from ifc_to_fds.deployment_config import validate_deployment_config


def test_local_desktop_mode_remains_available_without_api_key():
    assert validate_deployment_config({}) == "local"
    assert validate_deployment_config({"IFCFDS_ENV": "testing"}) == "testing"


@pytest.mark.parametrize(
    "mode",
    ["staging", "production"],
)
def test_network_mode_rejects_missing_and_short_key(mode):
    with pytest.raises(RuntimeError, match="IFCFDS_API_KEY"):
        validate_deployment_config({"IFCFDS_ENV": mode})
    with pytest.raises(RuntimeError, match="IFCFDS_API_KEY"):
        validate_deployment_config(
            {"IFCFDS_ENV": mode, "IFCFDS_API_KEY": "weak", "IFCFDS_ALLOWED_HOSTS": "api.example.org"}
        )


@pytest.mark.parametrize(
    "hosts",
    ["", "*", "api.example.org,*", "https://api.example.org", "api.example.org/path"],
)
def test_network_mode_requires_explicit_host_allowlist(hosts):
    with pytest.raises(RuntimeError, match="IFCFDS_ALLOWED_HOSTS"):
        validate_deployment_config(
            {
                "IFCFDS_ENV": "production",
                "IFCFDS_API_KEY": "a" * 40,
                "IFCFDS_ALLOWED_HOSTS": hosts,
            }
        )


def test_network_mode_accepts_explicit_operator_credentials():
    assert (
        validate_deployment_config(
            {
                "IFCFDS_ENV": "staging",
                "IFCFDS_API_KEY": "a" * 40,
                "IFCFDS_ALLOWED_HOSTS": "staging.example.org,api.example.org",
            }
        )
        == "staging"
    )


def test_undefined_mode_fails_instead_of_falling_back_to_local():
    with pytest.raises(RuntimeError, match="Invalid IFCFDS_ENV"):
        validate_deployment_config({"IFCFDS_ENV": "prod"})


def test_api_import_refuses_production_without_credentials():
    environ = os.environ.copy()
    environ["IFCFDS_ENV"] = "production"
    environ["IFCFDS_ALLOWED_HOSTS"] = "api.example.org"
    environ.pop("IFCFDS_API_KEY", None)
    result = subprocess.run(
        [sys.executable, "-c", "from ifc_to_fds import server"],
        env=environ,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "IFCFDS_API_KEY" in result.stderr
