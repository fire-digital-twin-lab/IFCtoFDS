FROM python:3.12.16-slim-trixie@sha256:962f801b08c870ac2a51b72bf02dae38c9a4162319e5e882ec244e198188d54e

# uv 0.13.7 is pinned by immutable OCI digest; uv.lock pins Python dependencies.
# Patches for scanner-confirmed Debian Trixie OS CVEs.
# Exact package versions are intentional: fail closed if a secured repository
# no longer provides them rather than silently rebuilding with vulnerable ones.
# apt/libapt-pkg7.0: CVE-2026-109518; zlib1g: CVE-2026-76844/85091.
RUN set -eu; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      apt=3.0.4 \
      libapt-pkg7.0=3.0.4 \
      'zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1'; \
    dpkg-query -W -f='${Version}\n' apt | grep -Fx '3.0.4'; \
    dpkg-query -W -f='${Version}\n' libapt-pkg7.0 | grep -Fx '3.0.4'; \
    dpkg-query -W -f='${Version}\n' zlib1g | grep -Fx '1:1.3.dfsg+really1.3.1-1+deb13u1'; \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN groupadd --gid 10001 ifctofds \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin ifctofds

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-install-project --no-editable

COPY ifc_to_fds ./ifc_to_fds
COPY js ./js
COPY css ./css
COPY index.html guide.html ./

RUN uv sync --locked --no-editable \
    && mkdir -p /var/lib/ifctofds/jobs \
    && chown -R 10001:10001 /var/lib/ifctofds

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"]

CMD ["python", "-m", "ifc_to_fds", "serve", "--host", "0.0.0.0", "--port", "8000"]
