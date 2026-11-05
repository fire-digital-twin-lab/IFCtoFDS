"""Fail-closed guard for deployments exposed beyond a developer workstation.

This intentionally does not claim multi-tenant authorization, TLS enforcement,
or full production security. Those remain separate acceptance requirements.
"""

import os
from typing import Mapping


_SAFE_MODES = frozenset({"local", "development", "test", "testing"})
_NETWORK_MODES = frozenset({"staging", "production"})


def validate_deployment_config(environ: Mapping[str, str] | None = None) -> str:
    """Reject unsafe staging/production authentication and Host configuration.

    The default is explicitly local-only: do not infer a production environment
    from a hostname, and never silently allow anonymous /api/* in network mode.
    """
    env = os.environ if environ is None else environ
    mode = env.get("IFCFDS_ENV", "local").strip().lower()
    if mode not in _SAFE_MODES | _NETWORK_MODES:
        raise RuntimeError(
            "Invalid IFCFDS_ENV; use local, development, test, testing, staging or production"
        )
    if mode in _NETWORK_MODES:
        key = env.get("IFCFDS_API_KEY", "")
        if len(key) < 32 or not key.strip() or key != key.strip():
            raise RuntimeError(
                "Staging/production requires IFCFDS_API_KEY of at least 32 "
                "non-whitespace characters, without leading/trailing spaces"
            )

        allowed = env.get("IFCFDS_ALLOWED_HOSTS", "")
        hosts = [part.strip().lower() for part in allowed.split(",")]
        if not hosts or any(not host or host == "*" for host in hosts):
            raise RuntimeError(
                "Staging/production requires explicit IFCFDS_ALLOWED_HOSTS; '*' is prohibited"
            )
        for host in hosts:
            if (
                "/" in host or "\\" in host or "@" in host
                or " " in host or "\n" in host or "\r" in host
                or "://" in host
            ):
                raise RuntimeError("IFCFDS_ALLOWED_HOSTS must contain hostnames, not URLs")
    return mode
