FROM python:3.12.16-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN groupadd --gid 10001 ifctofds \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin ifctofds

COPY pyproject.toml README.md LICENSE ./
COPY ifc_to_fds ./ifc_to_fds
COPY js ./js
COPY css ./css
COPY index.html guide.html ./

RUN python -m pip install --no-cache-dir . \
    && mkdir -p /var/lib/ifctofds/jobs \
    && chown -R 10001:10001 /var/lib/ifctofds

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"]

CMD ["python", "-m", "ifc_to_fds", "serve", "--host", "0.0.0.0", "--port", "8000"]
