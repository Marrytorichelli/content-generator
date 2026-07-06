# syntax=docker/dockerfile:1

# Production-friendly single-image build.
# - Uses slim base
# - Installs only minimal OS packages
# - Installs Python deps from requirements.txt (pinned)
# - Runs as non-root

FROM python:3.9-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Some networks block plain HTTP to Debian mirrors. Force HTTPS.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
  && sed -i 's|http://security.debian.org|https://security.debian.org|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
  && sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list 2>/dev/null || true \
  && sed -i 's|http://security.debian.org|https://security.debian.org|g' /etc/apt/sources.list 2>/dev/null || true

# System deps:
# - curl: Docker HEALTHCHECK
# - ca-certificates: HTTPS calls (FireCrawl, etc.)
# - tini: proper signal handling
# TODO(DevOps): Playwright in Docker requires:
# - installing browser binaries (`python -m playwright install --with-deps chromium`)
# - and/or installing system libraries required by Chromium
# Prefer using the official Playwright base image for production if you want fewer surprises:
#   mcr.microsoft.com/playwright/python:<tag>
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      tini \
  && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 10001 appuser

WORKDIR /app

# Install deps first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r /app/requirements.txt

# --- Playwright Chromium for in-container ingestion ---
# The /ingestion/crawl endpoint uses Playwright. We install Chromium + all required
# system libraries so the endpoint works out of the box. To skip this (smaller image)
# remove the block below and run ingestion from a dedicated worker container instead.
#
# TODO(DevOps): For production, consider the official Playwright base image
# (includes browsers + deps): `mcr.microsoft.com/playwright/python:<tag>`
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
      libnss3 \
      libatk1.0-0 \
      libatk-bridge2.0-0 \
      libcups2 \
      libdrm2 \
      libxkbcommon0 \
      libxcomposite1 \
      libxdamage1 \
      libxfixes3 \
      libxrandr2 \
      libgbm1 \
      libasound2 \
      libpangocairo-1.0-0 \
      libpango-1.0-0 \
      libgtk-3-0 \
      fonts-liberation \
  && rm -rf /var/lib/apt/lists/*

# Install browsers into a shared location so the non-root user can use them.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} \
  && python -m playwright install --with-deps chromium \
  && chmod -R a+rx ${PLAYWRIGHT_BROWSERS_PATH}

# Copy app code
COPY app /app/app
COPY scripts/start.sh /app/scripts/start.sh
COPY pyproject.toml /app/pyproject.toml
RUN chmod +x /app/scripts/start.sh

# Expose port (runtime-configured via APP_PORT)
EXPOSE 8000

# Healthcheck hits FastAPI liveness endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${APP_PORT:-8000}/healthz" || exit 1

USER appuser

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/scripts/start.sh"]
