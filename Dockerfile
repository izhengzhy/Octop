# =============================================================================
# Octop — Multi-stage Docker Build
#
# Stage 1: Build the React/TypeScript dashboard frontend
# Stage 2: Python runtime with the application + pre-built frontend
#
# Usage:
#   docker build -t octop:latest .
#   docker run -d -p 8088:8088 -v octop-data:/data/.octop -e HOME=/data octop:latest
#
# Or use docker-compose:
#   docker compose -f deploy/docker-compose.yml up -d
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — Frontend Build
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /build/dashboard

COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --prefer-offline --no-audit

COPY dashboard/ ./

RUN mkdir -p ../src/octop/dashboard

# Skip full tsc in the image build; vite/esbuild handles production bundling.
RUN NODE_ENV=production NODE_OPTIONS="--max-old-space-size=4096" npx vite build


# ---------------------------------------------------------------------------
# Stage 2 — Python Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL maintainer="OrcaKit Team"
LABEL org.opencontainers.image.title="Octop"
LABEL org.opencontainers.image.description="Smarter self-hosted AI assistant — multi-user, multi-agent."
LABEL org.opencontainers.image.source="https://github.com/TencentCloud/orca"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/data \
    OCTOP_BIND_HOST=0.0.0.0 \
    OCTOP_PORT=8088 \
    OCTOP_LOG_LEVEL=info

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY --from=frontend-builder /build/src/octop/dashboard/ ./src/octop/dashboard/

COPY .env.example ./
COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[browser]" \
    && playwright install --with-deps chromium \
    && apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/* /tmp/* \
    && find /root/.cache -mindepth 1 -maxdepth 1 ! -name 'ms-playwright' -exec rm -rf {} +

RUN mkdir -p /data/.octop

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD ["sh", "-c", "curl -f http://localhost:${OCTOP_PORT:-8088}/api/health || exit 1"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD []
