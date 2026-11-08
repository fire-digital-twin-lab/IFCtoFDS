"""Static deployment regressions for the production container contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_compose_requires_explicit_public_host_api_key_secret_and_tls():
    compose = (ROOT / "compose.production.yml").read_text(encoding="utf-8")
    assert "IFCFDS_ENV: production" in compose
    assert "IFCFDS_PUBLIC_HOST:?set IFCFDS_PUBLIC_HOST" in compose
    assert "IFCFDS_PUBLIC_HOST:?set IFCFDS_PUBLIC_HOST},127.0.0.1,localhost" in compose
    assert "IFCFDS_API_KEY_FILE:?set IFCFDS_API_KEY_FILE" in compose
    assert "IFCFDS_API_KEY:" not in compose
    assert "/run/secrets/api_key" in compose
    assert "IFCFDS_TLS_CERT_DIR:?set IFCFDS_TLS_CERT_DIR" in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "IFCFDS_JOB_ROOT: /var/lib/ifctofds/jobs" in compose


def test_proxy_contract_enforces_tls_and_does_not_publish_app_port():
    compose = (ROOT / "compose.production.yml").read_text(encoding="utf-8")
    proxy = (ROOT / "deploy" / "nginx.conf.template").read_text(encoding="utf-8")
    assert 'ports:\n      - "80:80"\n      - "443:443"' in compose
    assert 'expose:\n      - "8000"' in compose
    assert '"8000:8000"' not in compose
    assert "ssl_certificate /etc/nginx/tls/fullchain.pem;" in proxy
    assert "ssl_certificate_key /etc/nginx/tls/privkey.pem;" in proxy
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in proxy
    assert "Strict-Transport-Security" in proxy
    assert "limit_req zone=ifctofds_api" in proxy


def test_runtime_image_uses_non_root_application_user():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12.16-slim-bookworm")
    assert "ghcr.io/astral-sh/uv@sha256:" in dockerfile
    assert "COPY pyproject.toml uv.lock README.md LICENSE ./" in dockerfile
    assert "uv sync --locked --no-editable" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert '--host", "0.0.0.0"' in dockerfile
    assert "/api/health" in dockerfile
