FROM python:3.12.16-slim-trixie@sha256:962f801b08c870ac2a51b72bf02dae38c9a4162319e5e882ec244e198188d54e AS runtime

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

# Optional target (`docker build --target solver`): the runtime image plus FDS 6.11.1 for the solver gates.
# The official Linux release is a shell header followed by a gzip tar. Instead of running its interactive
# installer, check the SHA-256 of the whole file (the digest GitHub publishes for the release asset), cut the
# tar out exactly as the installer does, keep only the OpenMP solver and its bundled MPI runtime, and check the
# solver binary's hash too.
FROM runtime AS solver
ARG FDS_INSTALLER_URL=https://github.com/firemodels/fds/releases/download/FDS-6.11.1/FDS-6.11.1_SMV-6.11.2_lnx.sh
ARG FDS_INSTALLER_SHA256=ba8793b974150fdb778b3db0b69ab8db4e4668d5c52987a317e7f5ed58102ea0
ARG FDS_BINARY_SHA256=5e7cab038d1dbe05547a5dd6ba0ddfce9d55f58ae4d86494acfaf6bc7f6c7d57
USER root
RUN set -eu;     python -c "import hashlib, sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/tmp/fds.sh'); digest = hashlib.sha256(open('/tmp/fds.sh', 'rb').read()).hexdigest(); sys.exit(0 if digest == sys.argv[2] else 'FDS installer hash mismatch: ' + digest)"       "$FDS_INSTALLER_URL" "$FDS_INSTALLER_SHA256";     skip="$(awk '/^__TARFILE_FOLLOWS__/ { print NR + 1; exit 0 }' /tmp/fds.sh)";     mkdir -p /opt/fds;     tail -n +"$skip" /tmp/fds.sh | tar -xz --strip-components=1 -C /opt/fds --wildcards '*/bin/fds_openmp' '*/bin/intelmpi';     rm -f /tmp/fds.sh;     echo "$FDS_BINARY_SHA256  /opt/fds/bin/fds_openmp" | sha256sum -c -;     chmod -R a-w /opt/fds

ENV IFCFDS_SOLVER=/opt/fds/bin/fds_openmp     LD_LIBRARY_PATH=/opt/fds/bin/intelmpi/lib:/opt/fds/bin/intelmpi/lib/prov     I_MPI_ROOT=/opt/fds/bin/intelmpi     FI_PROVIDER_PATH=/opt/fds/bin/intelmpi/prov     I_MPI_FABRICS=shm

USER 10001:10001

# `docker build` without --target builds the last stage: keep that the plain runtime image, without FDS.
FROM runtime AS image
