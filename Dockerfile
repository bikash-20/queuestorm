# syntax=docker/dockerfile:1.6
# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — builder: install deps into a virtualenv we can copy later
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build deps (only needed in builder stage)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime: minimal image, non-root user
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    PORT=8000 \
    HOST=0.0.0.0

# Create non-root user
RUN groupadd --system --gid 1001 appuser \
    && useradd  --system --uid 1001 --gid appuser --home /app --shell /sbin/nologin appuser

# System deps for runtime (psutil needs no native libs, but keep tini for signal handling)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${APP_HOME}

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy source
COPY --chown=appuser:appuser app/ ${APP_HOME}/app/
COPY --chown=appuser:appuser pytest.ini ${APP_HOME}/

USER appuser

EXPOSE 8000

# Container-level healthcheck — pings the deep /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); \
sys.exit(0 if r.getcode() == 200 else 1)"

# tini handles PID 1 / signal forwarding cleanly
ENTRYPOINT ["/usr/bin/tini", "--"]

# Single worker is fine for this workload; --proxy-headers respects X-Forwarded-*
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--workers", "1"]
