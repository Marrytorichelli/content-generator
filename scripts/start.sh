#!/usr/bin/env sh
set -eu

: "${APP_HOST:=0.0.0.0}"
: "${APP_PORT:=8000}"
: "${UVICORN_WORKERS:=1}"
: "${UVICORN_TIMEOUT_KEEP_ALIVE:=5}"

# TODO(DevOps): in production, consider:
# - running behind an ingress / reverse proxy
# - setting UVICORN_WORKERS based on CPU (or switching to gunicorn+uvicorn workers)
# - adding structured tracing/metrics exporters

exec uvicorn app.main:app \
  --host "${APP_HOST}" \
  --port "${APP_PORT}" \
  --workers "${UVICORN_WORKERS}" \
  --timeout-keep-alive "${UVICORN_TIMEOUT_KEEP_ALIVE}"
